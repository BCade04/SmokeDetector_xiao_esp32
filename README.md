#### This program was intended to practice a bunch of new concepts for me as a beginner with the intent of producing something that's actually usefull.
This is a program loaded on and ESP32C3 XIAO that will notify me if my smoke detectors at home ativate or if my home loses utility power.
- In this program I successfully, perhaps not in the most elegant or efficient way, implemented:
  - Connect the esp32 to the internet.
  - Sync clock to NTP server.
  - Periodically re-sync the clock.
  - Periodically verify continued wifi connectivity.
  - Monitor the output from a relay interfaced to my smoke detectors.
  - Monitor utility power (esp32 is ups powered)
  - Perform daily self test of inputs to ensure inputs will reliably detect a change when it matters most.
  - Send status emails for: 
    - Failed or successfull clock syncs
    - Failed or successfull input tests
    - Smoke detectors activated
    - Smoke detectors returned to normal
    - Utility power loss
    - Utility power returned to normal
