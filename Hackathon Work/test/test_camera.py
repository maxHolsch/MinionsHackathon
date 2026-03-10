import cv2
import time
import base64
import anthropic

import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

def analyze_photo(filepath):
    """Send photo to Claude and return what the user is holding."""
    with open(filepath, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Recognize what user is holding and send back the message",
                    },
                ],
            }
        ],
    )
    return message.content[0].text


print("Camera test — USB connected")
print("  1 -> capture photo and analyze with Claude")
print("  q -> quit")

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open camera.")
    exit(1)

print("Camera opened. Live preview running...")

photo_count = 0

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to read frame.")
            break

        cv2.imshow("Camera Preview", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('1'):
            photo_count += 1
            filename = f"photo_{photo_count}_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            print(f"Photo saved: {filename}")
            print("Sending to Claude for analysis...")
            try:
                response = analyze_photo(filename)
                print(f"Claude: {response}")
            except Exception as e:
                print(f"API error: {e}")
        elif key == ord('q'):
            print("Quitting.")
            break
finally:
    cap.release()
    cv2.destroyAllWindows()
