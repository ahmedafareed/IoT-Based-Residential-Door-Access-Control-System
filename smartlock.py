import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import time
import re
import RPi.GPIO as GPIO
import cv2
import numpy as np
import sys
import pandas as pd 
# Email configuration
smtp_server = "smtp.gmail.com"
smtp_port = 587
imap_server = "imap.gmail.com"
sender_email = "ahmedamfareed@gmail.com"
sender_password = "akzz dphi smip xqek"
receiver_email = "s-ahmed_farid@zewailcity.edu.eg"

# GPIO configuration
led_pin = 18  # GPIO pin connected to the LED
GPIO.setmode(GPIO.BCM)
GPIO.setup(led_pin, GPIO.OUT)

# Function to send an email with an image attachment
def send_email_with_image(image_path):
    subject = "Human Detected! Would You Like to open the door?"
    body = "A human has been detected. Please reply with 'yes' or 'no'."

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    # Attach the image
    with open(image_path, "rb") as image_file:
        image = MIMEImage(image_file.read(), name=image_path)
        message.attach(image)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email with image sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
def check_for_reply():
    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(sender_email, sender_password)
        mail.select("inbox")

        status, messages = mail.search(None, f'(UNSEEN FROM "{receiver_email}")')
        if status == "OK":
            for num in messages[0].split():
                status, data = mail.fetch(num, "(RFC822)")
                if status == "OK":
                    msg = email.message_from_bytes(data[0][1])
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = msg.get_payload(decode=True).decode()
                    
                    
                    yes_keywords = ['yes', 'yep', 'yeah', 'okay']
                    no_keywords = ['no', 'nope', 'nah']
                    
                    for line in body.lower().splitlines():
                        line = line.strip() # added strip to remove any leading/trailing whitespaces
                        print(f"Debug: Line (lowercase): {line}")
                        df = pd.DataFrame({'text': [line]})

                        for keyword in no_keywords:
                             if df['text'].str.fullmatch(rf'\s*{keyword}\s*', case = False).any():
                                mail.store(num, '+FLAGS', r'\Seen')
                                print("User replied: NO (using pandas)")
                                mail.logout()
                                return "no"

                        for keyword in yes_keywords:
                             if df['text'].str.fullmatch(rf'\s*{keyword}\s*', case = False).any():
                                mail.store(num, '+FLAGS', r'\Seen')
                                print("User replied: YES (using pandas)")
                                mail.logout()
                                return "yes"

                    mail.store(num, '+FLAGS', r'\Seen')
        mail.logout()

    except Exception as e:
        print(f"Error checking for reply: {e}")
    return None


# Function to turn the LED on
def turn_led_on():
    GPIO.output(led_pin, GPIO.HIGH)
    print("LED is ON")

# Function to turn the LED off
def turn_led_off():
    GPIO.output(led_pin, GPIO.LOW)
    print("LED is OFF")

# Human detection function
def detect_human():
    # Load the pre-trained model and configuration
    model_weights = "mobilenet_iter_73000.caffemodel"
    model_config = "deploy.prototxt"
    net = cv2.dnn.readNetFromCaffe(model_config, model_weights)

    # Load the COCO class labels
    with open("coco.names", "r") as f:
        classes = f.read().strip().split("\n")

    # Initialize the camera
    camera = cv2.VideoCapture(0)  # Use 0 for the default USB camera

    # Wait for the camera to warm up
    if not camera.isOpened():
        print("Error: Could not open camera.")
        exit()

    while True:
        # Read a frame from the camera
        ret, frame = camera.read()
        if not ret:
            print("Failed to capture frame")
            break

        # Get the frame dimensions
        (h, w) = frame.shape[:2]

        # Prepare the frame for the model (resize and normalize)
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
        net.setInput(blob)

        # Perform object detection
        detections = net.forward()

        # Loop over the detections
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]

            # Filter out weak detections
            if confidence > 0.5:  # Adjust the confidence threshold
                class_id = int(detections[0, 0, i, 1])

                # Check if the detected object is a person (class_id == 15 for COCO)
                if class_id == 15:
                    # Get the bounding box coordinates
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")

                    # Draw the bounding box and label
                    cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 255, 0), 2)
                    label = f"Human: {confidence:.2f}%"
                    cv2.putText(frame, label, (startX, startY - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                    # Print a message to the console
                    print("Human detected! Capturing image...")

                    # Capture and save the frame as an image
                    image_filename = f"human_detected_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(image_filename, frame)
                    print(f"Image saved as {image_filename}")

                    # Release the camera and close windows
                    camera.release()
                    cv2.destroyAllWindows()

                    # Return the image filename
                    return image_filename

        # Display the frame
        cv2.imshow("Human Detection", frame)

        # Exit on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release the camera and close windows
    camera.release()
    cv2.destroyAllWindows()
    return None
# Main logic
def main():
    # Detect human and capture image
    image_filename = detect_human()
    if image_filename:
        # Send email with the captured image
        send_email_with_image(image_filename)

        # Wait for user reply
        print("Waiting for user reply...")
        while True:
            reply = check_for_reply()
            if reply == "yes":
                print("User agreed! Turning the LED ON.")
                turn_led_on()
                break
            elif reply == "no":
                print("User disagreed! Turning the LED OFF.")
                turn_led_off()
                break
            time.sleep(10)  # Wait 10 seconds before checking again

if __name__ == "__main__":
    main()
