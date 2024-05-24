from pynput import keyboard
import os
import json
import tools.functions as functions
import inspect
from openai import OpenAI
import requests
from app_utils import *
import datetime
from tools.MySocalApp import create_google_calendar_event
from tools.contacts import Contacts
from tools.mail import Mail
from tools.sms import SMS
from tools.location import search_location_in_maps
from tools.executecommand import execute_command
from tools.executecommand import generate_and_execute_applescript
from tools.Calendar import Calendar
import pytesseract
import threading
import time

# Check if the key exists
if "OPENAI_API_KEY" not in os.environ:
    print("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable first.")

# get openai api key from environment variable
client = OpenAI()
api_key = os.environ.get("OPENAI_API_KEY")

def add_functions_to_available_functions(Class):
    class_name = Class.__name__
    # Get all members of the functions module
    members = inspect.getmembers(Class)
    # load all functions from the Contacts class
    for name, member in members:
        # print (name)
        # Check if the member is a method
        if inspect.isfunction(member):
            # Add the method to the available_functions dictionary
            available_functions[name] = member

def load_tools():
    # load tools from tools.json
    with open("tools/tools.json", "r") as file:
        available_tools = json.load(file)['tools']

    # Get all members of the tools module
    members = inspect.getmembers(functions)
    # load all functions from tools module
    for name, member in members:
        # Check if the member is a function
        if inspect.isfunction(member):
            # Add the function to the available_functions dictionary
            available_functions[name] = member


    # Add Contacts to available functions
    add_functions_to_available_functions (Contacts)
    add_functions_to_available_functions (Mail)
    add_functions_to_available_functions (SMS)
    add_functions_to_available_functions (Calendar)
    available_functions['search_location_in_maps'] = search_location_in_maps
    available_functions['execute_command'] = execute_command
    available_functions['generate_and_execute_applescript'] = generate_and_execute_applescript
    # add schedule_google_calendar_event from MySocalApp to available functions
    available_functions['create_google_calendar_event'] = create_google_calendar_event

    return available_tools, available_functions

# Send context to GPT-4 and ask for a list of actions
def get_context (image, app_name, window_name):
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

            # if function response is a list, then combine them into a single string
            if isinstance(function_response, list):
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


if __name__ == "__main__":
    today_date = datetime.date.today()
    
    available_functions = {}
    available_tools = {}

    available_tools, available_functions = load_tools()

    # System prompt
    system_prompt = f'''
    Today's date is {today_date}.
    You are an action recommendation assistant on MacOS. Based on the user’s context and screenshots, recommend and execute actions using the available tools. List all available actions from 1~n (don't show any irrelevant action), and let the user choose the action.
    1. Recommend actions that are available in the tools provided. Don't recommend actions that are not available in the tools.
    2. To get more available tools, first call function get_shortcuts to find out what shortcuts are available, and add them to available tools to recommend based on the context.
    3. You can recommend similar options that are available. For example if there is a meeting request you can recommend both Apple Calendar and Google Calendar.
    4. After user finished the action, always proactively suggest more actions for user to take based on current context.
    If you need more parameters to complete function calling, you can ask the user for more information. Don't call functions if you are unsure about the correctness of parameters.
    5. In your available tools, there is a function called run_shortcut, which runs a certain shortcut designated by the user. You can use this function to run any shortcut on the user's machine. e.g. run_shortcut("Start Pomodoro") would start a Pomodoro timer on the user's machine.
    6. On MacOS, if you can't find a function to do something, you can use generate_and_execute_applescript to generate an applescript and execute it.
    If a tool is not available then generate the code necessary to execute the action and then call the execute_command function to execute the code.
    7. ALWAYS RECOMMEND MORE RELEVANT ACTIONS TO TAKE AFTER COMPLETING AN ACTION.

    Return JSON response with the following key value pairs:
    Description: the description of the curent screenshot
    Actions: the list of actions that the user can take

    '''

    # Prepare system message for gpt4v
    system = {
        "role": "system",
        "content": [
            {
            "type": "text",
            "text": system_prompt,
            },
        ]
    }

    messages = [system]

    print ("Welcome to UtopiaOS Action Recommendation System! What would like me to do for you today? To get started, either tell me the task you try to complete, or simply press command + shift to recommend actions based on vision understanding!\n")

    # Main loop
    while True:
        user_input = input(">User: ")
        if user_input.lower() in ["exit", "quit"]:
            # Exit the program
            break
        else:
            messages.append(
                {
                    "role": "user",
                    "content": user_input,
                }
            )
            screenshot, app_name, window_name = get_active_window_screenshot()
            screenshot = screenshot.resize((screenshot.width, screenshot.height))
            updated_messages = get_context(screenshot, app_name, window_name)
            run_conversation(updated_messages)
