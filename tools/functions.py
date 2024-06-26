import requests
import json
import os
from tavily import TavilyClient
# import contacts
# import inspect

# contacts = contacts.Contacts()

# Get functions from contacts module
# members = inspect.getmembers(contacts)

# Get ACCESS_TOKEN from environment variable
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

import datetime
import platform
import subprocess
# from app_utils import run_applescript, run_applescript_capture
import pyautogui

calendar_app = "Calendar"

# function_schema = {
#     "name": "execute",
#     "description": "Executes code on the user's machine **in the users local environment** and returns the output",
#     "parameters": {
#         "type": "object",
#         "properties": {
#             "language": {
#                 "type": "string",
#                 "description": "The programming language (required parameter to the `execute` function)",
#                 "enum": [
#                     # This will be filled dynamically with the languages OI has access to.
#                 ],
#             },
#             "code": {"type": "string", "description": "The code to execute (required)"},
#         },
#         "required": ["language", "code"],
#     },
# }

# Example dummy function hard coded to return the same weather
# In production, this could be your backend API or an external API
def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location"""
    if "tokyo" in location.lower():
        return json.dumps({"location": "Tokyo", "temperature": "10", "unit": unit})
    elif "san francisco" in location.lower():
        return json.dumps({"location": "San Francisco", "temperature": "72", "unit": unit})
    elif "paris" in location.lower():
        return json.dumps({"location": "Paris", "temperature": "22", "unit": unit})
    else:
        return json.dumps({"location": location, "temperature": "unknown"})

# Function to call the external API for paraphrasing
def paraphrase_text(text, plan="paid", prefer_gpt="gpt3", custom_style="", language="EN_US"):
    url = "https://api-yomu-writer-470e5c0e3608.herokuapp.com/paraphrase"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "ACCESS_TOKEN": f"{ACCESS_TOKEN}"
    }
    payload = json.dumps({
        "text": text,
        "plan": plan,
        "prefer_gpt": prefer_gpt,
        "custom_style": custom_style,
        "language": language
    })

    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        # print (response.json())
        return response.json()  # Return the JSON response from the API
    else:
        return {"error": "Failed to fetch data", "status_code": response.status_code}

# def write_message_with_keyboard(message):
#     # Type and send the message
#     pyautogui.write(message)
#     return "Message sent successfully as: " + message
#     # pyautogui.press('return')

# run_shortcut function
def run_shortcut (shortcut: str) -> str:
    "Runs given shortcut"
    try:
        os.system ("shortcuts run " + "'" + shortcut +"'")
        return "Sucessfully run shortcut " + shortcut
    except Exception as e:
        print(f"An error occurred: {e}")
        return e

# Get a list of shortcuts
def get_shortcuts ():
    # stdout, stderr = os.system("shortcuts list")  # Execute command and store stdout &stderr

    # Execute the shell command and capture its output  
    output = subprocess.check_output(["shortcuts", "list"], universal_newlines=True)

    # Print the output
    output = output.split("\n")[:-1]
    return output

def web_search (query: str):
    """
    Searches the web for the given query
    """

    tavily = TavilyClient(api_key=TAVILY_API_KEY)
    response = tavily.search(query=query)
    # print (response["results"])
    context = [{"url": obj["url"], "content": obj["content"]} for obj in response["results"]]
    # print (context)
    return context

# web_search ("How to make a cake")