import requests

def chat_with_api(user_input, image_path=None):
    url = "http://127.0.0.1:8000/api/chat"
    data = {
        "user_input": user_input
    }
    
    files = {}
    if image_path:
        files["file"] = open(image_path, "rb")

    response = requests.post(url, data=data, files=files)

    if response.status_code == 200:
        # print("Response from API:")
        # print(response.json())
        return response.json()
    else:
        print("Failed to get response")
        print("Status code:", response.status_code)
        print("Response:", response.text)

    if image_path:
        files["file"].close()

if __name__ == "__main__":
    while True:
        user_input = input("\nUser: ")
        if user_input.lower() == "exit":
            break
        
        response = chat_with_api(user_input)
        # print assistant's response
        print ("\nAssistant: "+ response)
