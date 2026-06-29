import json
from pathlib import Path

# Provide data explicitly so we don't rely on regex reversions
replacements = [
    (r"D:\JARVIS\modules\whatsapp_handler.py", "                \"I don't have a phone number to send to. \"", "                \"I don't have a phone number to send to, sir. \""),
    (r"D:\JARVIS\modules\whatsapp_handler.py", "            return \"I don't have any message content. Please tell me what to write.\"", "            return \"I don't have any message content, sir. Please tell me what to write.\""),
    (r"D:\JARVIS\modules\whatsapp_handler.py", "                f\"The phone number '{phone}' doesn't look right. \"", "                f\"The phone number '{phone}' doesn't look right, sir. \""),
    (r"D:\JARVIS\modules\whatsapp_handler.py", "            return f\"WhatsApp message sent to {recipient_display}.\"", "            return f\"WhatsApp message sent to {recipient_display}, sir.\""),
    (r"D:\JARVIS\modules\whatsapp_handler.py", "                \"I was unable to send the WhatsApp message. \"", "                \"I was unable to send the WhatsApp message, sir. \""),
    
    (r"D:\JARVIS\modules\web_search.py", "            return \"What would you like me to search for?\"", "            return \"What would you like me to search for, sir?\""),
    (r"D:\JARVIS\modules\web_search.py", "                return f\"I couldn't find any quick answers for {query}.\"", "                return f\"I couldn't find any quick answers for {query}, sir.\""),
    (r"D:\JARVIS\modules\web_search.py", "            return \"I encountered an error while searching the web.\"", "            return \"I encountered an error while searching the web, sir.\""),
    (r"D:\JARVIS\modules\web_search.py", "            return \"What would you like me to search for?\"", "            return \"What would you like me to search for, sir?\""),
    (r"D:\JARVIS\modules\web_search.py", "            return f\"I have opened the search results for {query} on your screen.\"", "            return f\"I have opened the search results for {query} on your screen, sir.\""),
    (r"D:\JARVIS\modules\web_search.py", "            return \"I was unable to open the web browser.\"", "            return \"I was unable to open the web browser, sir.\""),
    
    (r"D:\JARVIS\modules\weather.py", "            return f\"I'm sorry. I couldn't find a location named {location}.\"", "            return f\"I'm sorry, sir. I couldn't find a location named {location}.\""),
    (r"D:\JARVIS\modules\weather.py", "        return f\"The weather in {location_display} is {weather_data}.\"", "        return f\"The weather in {location_display} is {weather_data}, sir.\""),
    (r"D:\JARVIS\modules\weather.py", "        return \"I apologize, but I'm having trouble connecting to the weather service.\"", "        return \"I apologize, sir, but I'm having trouble connecting to the weather service.\""),
    
    (r"D:\JARVIS\modules\vision.py", "            return \"I was unable to analyze the image.\"", "            return \"I was unable to analyze the image, sir.\""),
    (r"D:\JARVIS\modules\vision.py", "            return \"I was unable to answer the question about the image.\"", "            return \"I was unable to answer the question about the image, sir.\""),
    (r"D:\JARVIS\modules\vision.py", "            return \"No webcam found.\"", "            return \"No webcam found, sir.\""),
    (r"D:\JARVIS\modules\vision.py", "            return \"I cannot see you.\"", "            return \"I cannot see you, sir.\""),
    (r"D:\JARVIS\modules\vision.py", "            return \"No webcam found.\"", "            return \"No webcam found, sir.\""),
    
    (r"D:\JARVIS\modules\tts.py", "        return \"I have increased my speaking rate.\"", "        return \"I have increased my speaking rate, sir.\""),
    (r"D:\JARVIS\modules\tts.py", "        return \"I have decreased my speaking rate.\"", "        return \"I have decreased my speaking rate, sir.\""),
    
    (r"D:\JARVIS\modules\scheduler.py", "            return f\"Reminder set for {friendly_time}: {task}.\"", "            return f\"Reminder set for {friendly_time}: {task}, sir.\""),
    (r"D:\JARVIS\modules\scheduler.py", "            return \"I'm sorry. I couldn't understand that time format.\"", "            return \"I'm sorry, sir. I couldn't understand that time format.\""),
    (r"D:\JARVIS\modules\scheduler.py", "                            self.tts_callback(f\"I have a reminder for you: {r['task']}\")", "                            self.tts_callback(f\"Sir, I have a reminder for you: {r['task']}\")"),
    
    (r"D:\JARVIS\modules\powershell_handler.py", "            return \"I need a command to execute.\"", "            return \"I need a command to execute, sir.\""),
    (r"D:\JARVIS\modules\powershell_handler.py", "                    return \"Command executed successfully with no output.\"", "                    return \"Command executed successfully with no output, sir.\""),
    (r"D:\JARVIS\modules\powershell_handler.py", "                return f\"Execution complete. Output: {output[:500]}\"", "                return f\"Execution complete, sir. Output: {output[:500]}\""),
    (r"D:\JARVIS\modules\powershell_handler.py", "                return f\"I encountered an error executing the script. Details: {error[:200]}\"", "                return f\"I encountered an error executing the script, sir. Details: {error[:200]}\""),
    (r"D:\JARVIS\modules\powershell_handler.py", "            return \"The script execution timed out.\"", "            return \"The script execution timed out, sir.\""),
    (r"D:\JARVIS\modules\powershell_handler.py", "            return f\"I failed to execute the PowerShell command. Error: {str(exc)}\"", "            return f\"I failed to execute the PowerShell command, sir. Error: {str(exc)}\""),
    
    (r"D:\JARVIS\modules\news.py", "            return \"I couldn't find any news updates at the moment.\"", "            return \"I couldn't find any news updates at the moment, sir.\""),
    (r"D:\JARVIS\modules\news.py", "        report = \"Here are the top headlines for today:\\n\" + \"\\n\".join(headlines)", "        report = \"Sir, here are the top headlines for today:\\n\" + \"\\n\".join(headlines)"),
    (r"D:\JARVIS\modules\news.py", "        return \"I apologize, but I'm having trouble connecting to the news feed.\"", "        return \"I apologize, sir, but I'm having trouble connecting to the news feed.\""),
    
    (r"D:\JARVIS\modules\llm.py", "            error_msg = \"I'm having trouble reaching my reasoning engine.\"", "            error_msg = \"I'm having trouble reaching my reasoning engine, sir.\""),
    
    (r"D:\JARVIS\modules\iot_handler.py", "            return \"Home Assistant is not configured. Please add your token to the configuration.\"", "            return \"Home Assistant is not configured, sir. Please add your token to the configuration.\""),
    (r"D:\JARVIS\modules\iot_handler.py", "            return \"Which device should I control, and what should I do?\"", "            return \"Which device should I control, and what should I do, sir?\""),
    (r"D:\JARVIS\modules\iot_handler.py", "            return f\"Understood. I'm turning the {device} {action} now.\"", "            return f\"Understood, sir. I'm turning the {device} {action} now.\""),
    (r"D:\JARVIS\modules\iot_handler.py", "            return f\"I failed to control the {device}.\"", "            return f\"I failed to control the {device}, sir.\""),
    
    (r"D:\JARVIS\modules\image_gen.py", "            return \"Please tell me what you would like me to draw.\"", "            return \"Please tell me what you would like me to draw, sir.\""),
    (r"D:\JARVIS\modules\image_gen.py", "            return f\"I have finished drawing that for you. Generated via {source}.\"", "            return f\"I have finished drawing that for you, sir. Generated via {source}.\""),
    (r"D:\JARVIS\modules\image_gen.py", "            return \"I apologize, but I encountered an error while trying to generate that image.\"", "            return \"I apologize, sir, but I encountered an error while trying to generate that image.\""),
    
    (r"D:\JARVIS\modules\gallery.py", "            self.image_label.config(text=\"No images found in gallery.\")", "            self.image_label.config(text=\"No images found in gallery, sir.\")"),
    (r"D:\JARVIS\modules\gallery.py", "            return \"The gallery is empty.\"", "            return \"The gallery is empty, sir.\""),
    (r"D:\JARVIS\modules\gallery.py", "        return f\"Opening the gallery. I've found {len(self.images)} images.\"", "        return f\"Opening the gallery, sir. I've found {len(self.images)} images.\""),
    
    (r"D:\JARVIS\modules\email_handler.py", "            return \"I don't have a recipient address. Please specify who to send the email to.\"", "            return \"I don't have a recipient address, sir. Please specify who to send the email to.\""),
    (r"D:\JARVIS\modules\email_handler.py", "            return \"I don't have any content for the email. Please tell me what to write.\"", "            return \"I don't have any content for the email, sir. Please tell me what to write.\""),
    (r"D:\JARVIS\modules\email_handler.py", "            return f\"Email sent to {recipient_display}.\"", "            return f\"Email sent to {recipient_display}, sir.\""),
    (r"D:\JARVIS\modules\email_handler.py", "                \"I was unable to send the email. \"", "                \"I was unable to send the email, sir. \""),
    (r"D:\JARVIS\modules\email_handler.py", "            return \"I cannot access your inbox. Credentials are missing.\"", "            return \"I cannot access your inbox, sir. Credentials are missing.\""),
    (r"D:\JARVIS\modules\email_handler.py", "                return \"I couldn't search the inbox.\"", "                return \"I couldn't search the inbox, sir.\""),
    (r"D:\JARVIS\modules\email_handler.py", "                return \"Your inbox is empty.\"", "                return \"Your inbox is empty, sir.\""),
    (r"D:\JARVIS\modules\email_handler.py", "                return \"I couldn't retrieve any recent emails.\"", "                return \"I couldn't retrieve any recent emails, sir.\""),
    (r"D:\JARVIS\modules\email_handler.py", "            report = \"Here are your most recent emails:\\n\" + \"\\n\".join(results)", "            report = \"Sir, here are your most recent emails:\\n\" + \"\\n\".join(results)"),
    (r"D:\JARVIS\modules\email_handler.py", "            return f\"I encountered an error while reading your inbox.\"", "            return f\"I encountered an error while reading your inbox, sir.\""),
    
    (r"D:\JARVIS\modules\browser.py", "            return \"I need a URL to open.\"", "            return \"I need a URL to open, sir.\""),
    (r"D:\JARVIS\modules\browser.py", "            return f\"Opening {url}.\"", "            return f\"Opening {url}, sir.\""),
    (r"D:\JARVIS\modules\browser.py", "            return f\"I couldn't reach that website. Error: {str(exc)}\"", "            return f\"I couldn't reach that website, sir. Error: {str(exc)}\""),
    (r"D:\JARVIS\modules\browser.py", "            return \"What should I search for?\"", "            return \"What should I search for, sir?\""),
    (r"D:\JARVIS\modules\browser.py", "            return f\"Searching for '{query}'.\"", "            return f\"Searching for '{query}', sir.\""),
    (r"D:\JARVIS\modules\browser.py", "            return \"I encountered an error while trying to search.\"", "            return \"I encountered an error while trying to search, sir.\""),
    
    (r"D:\JARVIS\modules\automation.py", "            return \"Text typed.\"", "            return \"Text typed, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return f\"I was unable to type that text. {exc}\"", "            return f\"I was unable to type that text, sir. {exc}\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"Please tell me which application to open.\"", "            return \"Please tell me which application to open, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return f\"Opening {app_name}.\"", "            return f\"Opening {app_name}, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return f\"I couldn't find {app_name}. Please check the application is installed.\"", "            return f\"I couldn't find {app_name}, sir. Please check the application is installed.\""),
    (r"D:\JARVIS\modules\automation.py", "            return f\"I was unable to open {app_name}.\"", "            return f\"I was unable to open {app_name}, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"Volume increased.\"", "            return \"Volume increased, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I was unable to adjust the volume.\"", "            return \"I was unable to adjust the volume, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"Volume decreased.\"", "            return \"Volume decreased, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I was unable to adjust the volume.\"", "            return \"I was unable to adjust the volume, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"Audio mute toggled.\"", "            return \"Audio mute toggled, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I was unable to toggle mute.\"", "            return \"I was unable to toggle mute, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"Copied to clipboard.\"", "            return \"Copied to clipboard, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I was unable to copy to the clipboard.\"", "            return \"I was unable to copy to the clipboard, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I was unable to read the clipboard.\"", "            return \"I was unable to read the clipboard, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"Clipboard cleared.\"", "            return \"Clipboard cleared, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I was unable to clear the clipboard.\"", "            return \"I was unable to clear the clipboard, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return f\"File created at {p.name}.\"", "            return f\"File created at {p.name}, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I could not create the file.\"", "            return \"I could not create the file, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return f\"Folder {p.name} created.\"", "            return f\"Folder {p.name} created, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I could not create the folder.\"", "            return \"I could not create the folder, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return f\"Moved successfully to {Path(dest).name}.\"", "            return f\"Moved successfully to {Path(dest).name}, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I could not move the item.\"", "            return \"I could not move the item, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return f\"Renamed to {new_name}.\"", "            return f\"Renamed to {new_name}, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I could not rename the item.\"", "            return \"I could not rename the item, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return f\"Deleted {p.name}.\"", "            return f\"Deleted {p.name}, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I could not delete the item.\"", "            return \"I could not delete the item, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "                return \"That path is not a valid folder.\"", "                return \"That path is not a valid folder, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I could not read the folder contents.\"", "            return \"I could not read the folder contents, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            status = f\"System report. CPU usage is at {cpu} percent. Memory is at {ram} percent.\"", "            status = f\"System report, sir. CPU usage is at {cpu} percent. Memory is at {ram} percent.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I was unable to retrieve the system status.\"", "            return \"I was unable to retrieve the system status, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "                return f\"The active window is {window.title}.\"", "                return f\"The active window is {window.title}, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I couldn't identify the active window.\"", "            return \"I couldn't identify the active window, sir.\""),
    (r"D:\JARVIS\modules\automation.py", "            return \"I failed to retrieve the window information.\"", "            return \"I failed to retrieve the window information, sir.\""),
    
    (r"D:\JARVIS\main.py", "            speak_interruptible(\"Voice enrollment complete. Your identity is now secured.\")", "            speak_interruptible(\"Voice enrollment complete. Your identity is now secured, sir.\")"),
    (r"D:\JARVIS\main.py", "            speak_interruptible(\"Enrollment failed.\")", "            speak_interruptible(\"Enrollment failed, sir.\")"),
    (r"D:\JARVIS\main.py", "        speak_interruptible(\"Beginning enrollment. Please speak clearly for five seconds starting now.\")", "        speak_interruptible(\"Beginning enrollment. Please speak clearly for five seconds starting now, sir.\")"),
    (r"D:\JARVIS\main.py", "            speak_interruptible(\"WhatsApp integration is offline.\")", "            speak_interruptible(\"WhatsApp integration is offline, sir.\")"),
    (r"D:\JARVIS\main.py", "            speak_interruptible(\"Automation is offline.\")", "            speak_interruptible(\"Automation is offline, sir.\")"),
    (r"D:\JARVIS\main.py", "            response = \"What would you like me to type?\"", "            response = \"What would you like me to type, sir?\""),
    (r"D:\JARVIS\main.py", "            speak_interruptible(\"Automation is offline.\")", "            speak_interruptible(\"Automation is offline, sir.\")"),
    (r"D:\JARVIS\main.py", "            error_msg = \"I encountered an error processing that request. Please try again.\"", "            error_msg = \"I encountered an error processing that request, sir. Please try again.\""),

    (r"D:\JARVIS\modules\document_reader.py", "return f\"I cannot find the file at {file_path}.\"", "return f\"I cannot find the file at {file_path}, sir.\""),
    (r"D:\JARVIS\modules\document_reader.py", "return \"The PDF appears to be empty or contains only images.\"", "return \"The PDF appears to be empty or contains only images, sir.\""),
    (r"D:\JARVIS\modules\document_reader.py", "return f\"Failed to read the PDF. Error: {exc}\"", "return f\"I failed to read the PDF, sir. Error: {exc}\""),
    (r"D:\JARVIS\modules\document_reader.py", "return \"The document appears to be empty.\"", "return \"The document appears to be empty, sir.\""),
    (r"D:\JARVIS\modules\document_reader.py", "return f\"Failed to read the Word document. Error: {exc}\"", "return f\"I failed to read the Word document, sir. Error: {exc}\""),
    (r"D:\JARVIS\modules\document_reader.py", "return f\"I could not read the text file. Error: {exc}\"", "return f\"I could not read the text file, sir. Error: {exc}\""),
    (r"D:\JARVIS\modules\document_reader.py", "return f\"The {ext} file format is not supported yet.\"", "return f\"I do not support the {ext} file format yet, sir.\"")
]

import collections
files = collections.defaultdict(list)
for path, old, new in replacements:
    files[path].append((old, new))

for path, changes in files.items():
    p = Path(path)
    if not p.exists(): continue
    content = p.read_text(encoding="utf-8")
    for old, new in changes:
        if old in content:
            content = content.replace(old, new)
            print(f"Replaced in {p.name}")
        else:
            print(f"NOT FOUND: '{old}' in {p.name}")
    p.write_text(content, encoding="utf-8")
print("Done restoring.")
