import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import screen_brightness_control as sbc
from math import hypot

# Import platform-specific libraries for volume control
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
except ImportError:
    print("pycaw library not found. Volume control will not work. Please install with 'pip install pycaw'.")
    AudioUtilities = None
    IAudioEndpointVolume = None

# Set up volume control using pycaw (Windows only)
if AudioUtilities:
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        vol_range = volume.GetVolumeRange()
        min_vol = vol_range[0]
        max_vol = vol_range[1]
    except Exception as e:
        print(f"Error setting up volume control: {e}")
        volume = None

# Get screen width and height for cursor control
screen_width, screen_height = pyautogui.size()

# -------------------- Camera and Hand Tracking Setup -------------------- #
cap = cv2.VideoCapture(0)  # Use the default webcam
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.5)
mp_draw = mp.solutions.drawing_utils

# Finger tip IDs from MediaPipe's hand landmarks
finger_tip_ids = [8, 12, 16, 20]

# State variable for scrolling
is_scrolling = False

# Function to check if a finger is extended
def fingers_up(landmarks):
    fingers = []
    # Thumb check (x-coordinate check for right hand)
    if landmarks[4].x < landmarks[3].x:
        fingers.append(1)
    else:
        fingers.append(0)
    
    # Other four fingers check (y-coordinate check)
    for id in finger_tip_ids:
        if landmarks[id].y < landmarks[id - 2].y:
            fingers.append(1)
        else:
            fingers.append(0)
    return fingers

# -------------------- Main Loop -------------------- #
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Flip the frame for a more intuitive user experience
    frame = cv2.flip(frame, 1)
    
    # Convert the frame to RGB for MediaPipe processing
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Process the frame to detect hands
    results = hands.process(rgb_frame)
    
    # Check if hands are detected
    if results.multi_hand_landmarks:
        for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
            # Draw landmarks on the detected hand
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            
            # Get the label (left or right) for the detected hand
            hand_label = handedness.classification[0].label.upper()
            
            # Create a list of landmarks for easier access
            lm_list = []
            for id, lm in enumerate(hand_landmarks.landmark):
                h, w, c = frame.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                lm_list.append([id, cx, cy])
            
            # Determine which hand it is and control the corresponding function
            if hand_label == 'RIGHT':
                # Right hand controls cursor, brightness, and scroll
                
                # Check which fingers are up
                my_fingers = fingers_up(hand_landmarks.landmark)
                
                # If only index finger is up, control the cursor
                if my_fingers[1] == 1 and sum(my_fingers) == 1:
                    is_scrolling = False # Reset scrolling state
                    x1, y1 = lm_list[8][1], lm_list[8][2]
                    
                    # Normalize the finger position to screen coordinates
                    mouse_x = np.interp(x1, [30, w - 30], [0, screen_width])
                    mouse_y = np.interp(y1, [30, h - 30], [0, screen_height])
                    
                    pyautogui.moveTo(mouse_x, mouse_y)
                    
                    # Draw a circle on the index finger tip to indicate cursor mode
                    cv2.circle(frame, (x1, y1), 10, (0, 255, 255), cv2.FILLED)
                    cv2.putText(frame, 'Cursor Mode', (100, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 255), 2)
                    
                    # If thumb and index finger are close, simulate a click
                    x2, y2 = lm_list[4][1], lm_list[4][2]
                    length = hypot(x2 - x1, y2 - y1)
                    if length < 25:
                        pyautogui.click()
                
                # If only thumb and index finger are up, control brightness
                elif my_fingers[0] == 1 and my_fingers[1] == 1 and sum(my_fingers) == 2:
                    is_scrolling = False # Reset scrolling state
                    x1, y1 = lm_list[4][1], lm_list[4][2]
                    x2, y2 = lm_list[8][1], lm_list[8][2]
                    
                    length = hypot(x2 - x1, y2 - y1)
                    
                    brightness_val = np.interp(length, [20, 200], [0, 100])
                    if sbc:
                        try:
                            sbc.set_brightness(brightness_val)
                        except Exception as e:
                            print(f"Could not set brightness: {e}")
                    
                    # Draw the brightness bar on the screen
                    bar_x = 50
                    bar_y = 150
                    bar_height = 250
                    
                    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 35, bar_y + bar_height), (0, 0, 255), 3)
                    filled_bar_y = np.interp(brightness_val, [0, 100], [bar_y + bar_height, bar_y])
                    cv2.rectangle(frame, (bar_x, int(filled_bar_y)), (bar_x + 35, bar_y + bar_height), (255, 255, 0), cv2.FILLED)
                    cv2.putText(frame, f'Brightness: {int(brightness_val)}%', (100, 150), cv2.FONT_HERSHEY_COMPLEX, 0.8, (255, 255, 0), 2)
                    cv2.putText(frame, 'Brightness Mode', (100, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 0), 2)
                    
                # If only index and middle fingers are up, perform auto-scroll
                elif my_fingers[1] == 1 and my_fingers[2] == 1 and sum(my_fingers) == 2:
                    if not is_scrolling:
                        pyautogui.press('down')
                        is_scrolling = True
                    cv2.putText(frame, 'Scroll Mode', (100, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 0), 2)
                
                else:
                    is_scrolling = False # Reset scrolling state if no valid gesture is detected
            
            elif hand_label == 'LEFT':
                # Left hand controls volume
                x1, y1 = lm_list[4][1], lm_list[4][2]
                x2, y2 = lm_list[8][1], lm_list[8][2]
                
                # Draw circles on the fingertips and a line connecting them
                cv2.circle(frame, (x1, y1), 10, (255, 0, 0), cv2.FILLED)
                cv2.circle(frame, (x2, y2), 10, (255, 0, 0), cv2.FILLED)
                cv2.line(frame, (x1, y1), (x2, y2), (255, 0, 0), 3)
                
                # Calculate the distance between the thumb and index finger tips
                length = hypot(x2 - x1, y2 - y1)
                
                vol_val = np.interp(length, [20, 200], [min_vol, max_vol])
                if volume:
                    try:
                        volume.SetMasterVolumeLevel(vol_val, None)
                    except Exception as e:
                        print(f"Could not set volume: {e}")
                
                # Draw the volume bar on the screen
                bar_x = w - 85
                bar_y = 150
                bar_height = 250
                
                vol_per = np.interp(length, [20, 200], [0, 100])
                
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 35, bar_y + bar_height), (0, 0, 255), 3)
                filled_bar_y = np.interp(vol_per, [0, 100], [bar_y + bar_height, bar_y])
                cv2.rectangle(frame, (bar_x, int(filled_bar_y)), (bar_x + 35, bar_y + bar_height), (0, 255, 0), cv2.FILLED)
                cv2.putText(frame, f'Volume: {int(vol_per)}%', (w - 200, 150), cv2.FONT_HERSHEY_COMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, 'Volume Mode', (w - 200, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 0), 2)
    
    else:
        is_scrolling = False # Reset scrolling state if no hands are detected

    # Display the final frame with all the overlays
    cv2.imshow('Hand Gesture Controls', frame)
    
    # Break the loop if the 'q' key is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the camera and destroy all windows
cap.release()
cv2.destroyAllWindows()
