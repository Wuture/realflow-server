import subprocess
import platform
from app_utils import run_applescript

class SMS:
    @staticmethod
    def send_sms(to: str, message: str) -> str:
        print ("Sending SMS to:", to, "with message:", message)

        """
        Sends an SMS message to the specified recipient using the Messages app.
        """
        # Check if the operating system is MacOS, as this functionality is MacOS-specific.
        if platform.system() != 'Darwin':
            return "This method is only supported on MacOS"
        
        # Remove any newline characters from the recipient number.
        to = to.replace("\n", "")
        # Escape double quotes in the message and recipient variables to prevent script errors.
        escaped_message = message.replace('"', '\\"')
        escaped_to = to.replace('"', '\\"')

        script = f"""
        tell application "Messages"                                                   
            set targetBuddy to buddy "{escaped_to}" of service 1                        
            send "{escaped_message}" to targetBuddy                                
        end tell 
        """
        try:
            run_applescript(script)
            return "SMS message sent"
        except subprocess.CalledProcessError:
            return "An error occurred while sending the SMS. Please check the recipient number and try again."
