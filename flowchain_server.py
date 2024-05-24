from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import inspect
from openai import OpenAI
from app_utils import *
import datetime
import tools.functions as functions
from tools.contacts import Contacts
from tools.mail import Mail
from tools.sms import SMS
from tools.location import search_google_maps
from tools.executecommand import execute_command, generate_and_execute_applescript
from tools.Calendar import Calendar
import pytesseract
import time
from PIL import Image

# Check if the key exists
if "OPENAI_API_KEY" not in os.environ:
    raise EnvironmentError("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable first.")

# Get OpenAI API key from environment variable
client = OpenAI()
api_key = os.environ.get("OPENAI_API_KEY")

app = FastAPI()

available_functions = {}
available_tools = {}

def add_functions_to_available_functions(Class):
    class_name = Class.__name__
    members = inspect.getmembers(Class)
    for name, member in members:
        if inspect.isfunction(member):
            available_functions[name] = member

def load_tools():
    with open("tools/tools.json", "r") as file:
        available_tools = json.load(file)['tools']
    members = inspect.getmembers(functions)
    for name, member in members:
        if inspect.isfunction(member):
            available_functions[name] = member
    add_functions_to_available_functions(Contacts)
    add_functions_to_available_functions(Mail)
    add_functions_to_available_functions(SMS)
    add_functions_to_available_functions(Calendar)
    # available_functions['search_location_in_maps'] = search_location_in_maps
    available_functions['execute_command'] = execute_command
    available_functions['generate_and_execute_applescript'] = generate_and_execute_applescript
    # available_functions['execute_python_code'] = execute_python_code
    # available_functions['generate_and_execute_python_code'] = generate_and_execute_python_code
    available_functions['search_google_maps'] = search_google_maps
    # available_functions['create_google_calendar_event'] = create_google_calendar_event
    # print (available_functions)
    return available_tools, available_functions

available_tools, available_functions = load_tools()

today_date = datetime.date.today()

system_prompt = f'''
Today's date is {today_date}.
You are an action recommendation assistant on macOS. You can do anything user asks you to do! Your primary goals are:

1. Respond to the user's query or context with a clear and concise message.
2. Given a query, list relevant actions from 1 to n, prioritizing actions by relevance and excluding any irrelevant ones. Chain actions together as a plan, allowing the user to confirm before execution.
3. Recommend only actions that are available within the tools and are highly likely to be useful to the user.
4. If more tools are needed, call the function `get_shortcuts` to find out which shortcuts are available, and add them to the list of tools available based on the context.
5. If additional parameters and information are needed to complete a function call, ask the user for the required details.
6. Use the `run_shortcut` function to execute any shortcut on the user's machine (e.g., `run_shortcut("Start Pomodoro")` starts a Pomodoro timer).
7. If a user query can be fulfilled by an AppleScript, generate the necessary code to execute the action and then call the `execute_command` function to run the code.
8. Always recommend more relevant actions to take after completing an action.
9. 

Respond in ONLY JSON format with the following key-value pairs:
- Response: Provide a response to the user's query based on the context.
- Actions: A list of available actions for the user to choose from.

Example JSON format:
{{
  "Response": "Your response to the user's query based on the context.",
  "Actions": [
    "1. Action one description",
    "2. Action two description",
    ...
  ]
}}
'''


system_message = {
    "role": "system",
    "content": [
        {
            "type": "text",
            "text": system_prompt,
        },
    ]
}

messages = [system_message]

# Send context to GPT-4 and ask for a list of actions
def get_context (image, app_name=None, window_name=None):
    global messages

    # print ("Preparing an response!\n")
    base64_image = encode_image(image)

    user_query =  {
        "role": "user",
        "content": [
            {
            "type": "text",
            "text": f"I am using {app_name} and on its {window_name}."
            },
            {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}",
                "detail":"low"
            }
            }
        ]
    }

    messages.append(user_query)

    return messages
    
def run_conversation(messages):
    # print (messages)
    # Step 1: send the conversation and available functions to the model
    # Time the request
    start_time = time.time()
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=messages,
        tools=available_tools,
        tool_choice="auto",  # auto is default, but we'll be explicit
        # output json
        temperature=0,
    )

    # pop the last message from the messages to conserve context windows.
    messages.pop()

    response_message = response.choices[0].message

    # print (response_message)

    tool_calls = response_message.tool_calls
    
    # Step 2: check if the model wanted to call a function
    # messages.append(response_message)  # extsend conversation with assistant's reply
    if tool_calls:
        messages.append(response_message)
        # Step 3: call the function
        # Note: the JSON response may not always be valid; be sure to handle errors
        # Step 4: send the info for each function call and function response to the model
        for tool_call in tool_calls:
            # print (tool_call)
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)

            # print("Calling function: ", function_name)

            # catch error and just append the error to the messages
            try:
                function_response = function_to_call(**function_args)
            except Exception as e:
                function_response = str(e)
                print(f"An error occurred: {e}")

            # If the response is a json, convert it to a string
            if isinstance(function_response, dict):
                function_response = json.dumps(function_response)

            # print (function_response)
            # # if function response is a list, then combine them into a single string
            if isinstance(function_response, list):
                # if the response is a list of dictionaries, convert them to strings
                for i, response in enumerate(function_response):
                    if isinstance(response, dict):
                        function_response[i] = json.dumps(response)
                # else convert the list to a string
                function_response = ",".join(function_response)

            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                }
            )  # extend conversation with function response
        second_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )  # get a new response from the model where it can see the function response
        second_message = second_response.choices[0]
        if second_message.message.content:
            # print("Response from the model after function call:")
            print(">Assistant: ", second_message.message.content)
        # print(second_message)
        # append the new message to the conversation
            # Prepare assistant message to append to the conversation
            assistant_message = {
                "role": "assistant",
                "content": second_message.message.content,
            }
            messages.append(assistant_message)
    else:
        if response_message.content is not None:
            # print("Response from the model: \n") 
            print(">Assistant: ", response_message.content)
            
            # Add assistant's response to the conversation
            assistant_message = {
                "role": "assistant",
                "content": response_message.content,
            }
            messages.append(assistant_message)
    end_time = time.time()
    print(f"Request took {end_time - start_time} seconds")

    # print (messages)
    return messages

# @app.post("/api/chat")
# async def chat(user_input: str = Form(...)):
#     global messages
#     messages.append({
#         "role": "user",
#         "content": user_input,
#     })

#     # # Get the active window and take a screenshot
#     # # screenshot, app_name, window_name = get_active_window_screenshot()

#     # # Take screenshot of the entire screen
#     # screenshot = pyautogui.screenshot()

#     # # reduce the size of the image proportionally to 50%
#     # screenshot.thumbnail((screenshot.width // 2, screenshot.height // 2))


#     # # Get the context
#     # messages = get_context(screenshot)

#     # Run the conversation
#     messages = run_conversation(messages)

#     # Get the last assistant message
#     assistant_message = messages[-1]

#     return assistant_message["content"]

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat(request: ChatRequest):
    global messages
    user_input = request.message
    messages.append({
        "role": "user",
        "content": user_input,
    })

    # Run the conversation (you need to implement this function)
    messages = run_conversation(messages)

    # Get the last assistant message
    assistant_message = messages[-1]

    # return {"response": assistant_message["content"]}
    print (assistant_message["content"])
    return assistant_message["content"]