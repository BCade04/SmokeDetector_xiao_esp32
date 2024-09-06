import network
import ntptime 
import time
import umail

from machine import Pin, reset, RTC, WDT 

from secrets import GOOGLE_PASSWORD, WIFI_SSID, WIFI_PASSWORD

# ----------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------#

# GLOBAL VARIABLES
SYNCED = True                                               # declare and initialize clock sync status

# ----------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------#

def main():   
    # main() function setup                                         
    global SYNCED                                           # make global variables available to main()     
    test = Pin(2, Pin.OUT)                                  # create instance of Pin object / output for performing input test (1st pin, bottom right)
    smoke_pin = Pin(4, Pin.IN, Pin.PULL_DOWN)               # create instance of Pin object / smoke detector input (3rd pin, bottom right)
    power_pin = Pin(5, Pin.IN, Pin.PULL_DOWN)               # create instance of Pin object / power status input (4th pin, bottom right)                                    
    rtc = RTC()                                             # create instance of RTC object / clock to timestamp emails
    wdt = WDT(timeout = 30000)                              # create instance of WDT object / watchdog timer to reset ESP32 if code hangs up


    # synchronize real time clock
    sync_clock(rtc)                                         # sync time with NTP server and adjust for timezone and DST
    if not SYNCED:
        sync_ticks = time.ticks_ms()                        # start counting for a clock sync retry

    # Initial bootup status email
    send_email(rtc, 1)                                      # bootup successfull email


    # Main while loop variables initialize
    wifi_ticks = time.ticks_ms()                            # declare variable for timing check_wifi function calls
    sync_triggered = False                                  # declare clock sync triggered variable...also used to trigger self test
    smoke_cycle_started = False                             # declare smoke detector activated email cycle status
    smoke_alarm = False                                     # declare variable to store smoke alarm status
    power_cycle_started = False                             # declare power failure email cycle status
    power_alarm = False                                     # declare varialbe to store power alarm status
   
    while True:

        # Periodically check that wifi is connected
        if time.ticks_diff(time.ticks_ms(), wifi_ticks) >= 60000:      
            check_wifi("check")                             # check wifi once per minute
            wifi_ticks = time.ticks_ms()                    # reset starting point for timing the check_wifi function call


        # Periodically sync the Real Time Clock
        cur_time = get_datetime(rtc)
        if cur_time[4] == 5 and not sync_triggered:         # check if time is 5:00 AM and that clock sync hasn't been triggered yet
            sync_triggered = True                           # set triggered status to True
            sync_clock(rtc)                                 # daily clock sync
            if not SYNCED:
                sync_ticks = time.ticks_ms()

        # If RTC failed to sync, try again every 10 minutes until successful
        elif not SYNCED:
            if time.ticks_diff(time.ticks_ms(), sync_ticks) >= 600000:
                sync_clock(rtc)


        # Periodically perform input test
        if cur_time[4] != 5 and sync_triggered:             # if it's not 5:00 AM and clock sync has been triggered
            test.value(1)                                   # turn on output to perform input test
            sync_triggered = False                          # reset triggered status
            time.sleep_ms(500)                              # give the relay a moment to change states
            

        # Detect smoke input state change
        if smoke_pin.value() == 0 and not smoke_alarm:    
            smoke_status = debounce(smoke_pin, wdt)
            smoke_alarm = not smoke_status
        elif smoke_pin.value() == 1 and smoke_alarm:
            smoke_status = debounce(smoke_pin, wdt)  
            smoke_alarm = smoke_status 

        # Detect power input state
        if  power_pin.value() == 0 and not power_alarm:
            power_status = debounce(power_pin, wdt)
            power_alarm = not power_status
        elif power_pin.value() == 1 and power_alarm:
            power_status = debounce(power_pin, wdt)
            power_alarm = not power_status


        # Input test Pass/Fail
        if test.value() == 1:

            # Smoke test pass/fail
            if not smoke_cycle_started and smoke_alarm:
                smoke_alarm = False  
                smoke_status = True                     
                smoke_test_passed = True
            else:
                smoke_test_passed = False

            # Power test pass/fail
            if not power_cycle_started and power_alarm:
                power_alarm = False
                power_status = True
                power_test_passed = True
            else:
                power_test_passed = False

            # Input test results email
            if smoke_test_passed and power_test_passed:
                send_email(rtc, 4)                         # input tests passed email
            elif smoke_test_passed and not power_test_passed:
                send_email(rtc, 5)                         # smoke test passed, power test failed email
            elif not smoke_test_passed and power_test_passed:
                send_email(rtc, 6)                         # smoke test failed, power test passed email
            elif not smoke_test_passed and not power_test_passed:
                send_email(rtc, 7)                         # input tests failed email

            test.value(0)                                  # turn off output to end self test  
            time.sleep_ms(500)                             # give the relay a moment to change states


        # Smoke alarm active
        if smoke_alarm:

            # Begin email cycle when smoke alarm activates
            if not smoke_cycle_started:                           
                send_email(rtc, 8)                          # smoke detectors active email
                smoke_cycle_started = True                  # set the cycle started status
                smoke_ticks = time.ticks_ms()               # start timing for the next email

            # Send email every 30 seconds while smoke alarm is active  
            elif smoke_cycle_started and time.ticks_diff(time.ticks_ms(), smoke_ticks) >= 30000: 
                send_email(rtc, 8)
                smoke_ticks = time.ticks_ms()

           
        # Smoke alarm normal
        elif not smoke_alarm:

            # Send email confirming smoke alarm has returned to normal
            if smoke_cycle_started:
                send_email(rtc, 9)                          # smoke detectors normal email
                smoke_cycle_started = False                 # reset the cycle started status


        # Utility power alarm active
        if power_alarm:

            # Begin email cycle when utility power alarm activates
            if not power_cycle_started:
                send_email(rtc, 10)                         # utility power is off email
                power_cycle_started = True                  # set the cycle started status
                power_ticks = time.ticks_ms()               # start timing for the next email

            # Send email every hour while utility power is off
            elif power_cycle_started and time.ticks_diff(time.ticks_ms(), power_ticks) >= 3600000:
                send_email(rtc, 10)
                power_ticks = time.ticks_ms()


        # Utility power normal
        elif not power_alarm:

            #Send email confirming Utility Power has been restored
            if power_cycle_started:
                send_email(rtc, 11)                         # utility power restored email
                power_cycle_started = False                 # reset the cycle started status

                
        time.sleep_ms(100)                                  # take a break microcontroller, you deserve it

        wdt.feed()                                          # reset WDT timer

# ----------------------------------------------------------------------------------------------------------------#
# ----------------------------------------------------------------------------------------------------------------#
    
def sync_clock(rtc):
    global SYNCED
    DST = False 

    # Try to sync with NTP server
    try:
        ntptime.settime()

    # Handle time sync failure
    except Exception:
        send_email(rtc, 2)
        SYNCED = False 
        return
    
    else:
        SYNCED = True                                       # Set sync status to indicate success
        sec = ntptime.time()                                # Seconds since epoch
        timezone_hour = 6                                   # Hours to offset from UTC to Central time
        timezone_sec = timezone_hour * 3600                 # Convert offset to seconds
        sec = int(sec - timezone_sec)                       # Seconds since epoch - offset
        
        # Correct local time using the sec variable as arg. Declare tuple for date/time variables
        (year, month, day, hour, minutes, seconds, weekday, yearday) = time.localtime(sec)  

    # Check if DST has started
    if year == 2024 and yearday >= 69 and yearday < 308:
        DST = True
    elif year == 2025 and yearday >= 68 and yearday < 307:
        DST = True
    elif year == 2026 and yearday >= 67 and yearday < 306:
        DST = True
    elif year == 2027 and yearday >= 73 and yearday < 304:
        DST = True
    elif year == 2028 and yearday >= 72 and yearday < 310:
        DST = True
    elif year == 2029 and yearday >= 71 and yearday < 309:
        DST = True
    elif year == 2030 and yearday >= 69 and yearday < 308:
        DST = True
    elif year == 2031 and yearday >= 68 and yearday < 307:
        DST = True
    elif year == 2032 and yearday >= 74 and yearday < 304:
        DST = True
    elif year == 2033 and yearday >= 73 and yearday < 310:
        DST = True
    elif year == 2034 and yearday >= 72 and yearday < 309:
        DST = True

    # Apply DST offset
    if DST:                                              
        hours = hour + 1                      
    else:
        hours = hour

    # Set RTC using synchronized, DST compensated variables
    rtc.datetime((year, month, day, weekday, hours, minutes, seconds, 0))    

    send_email(rtc, 3)                                      # clock sync successfull email       

def get_datetime(rtc):
    (yyyy, mm, dd, wd, h, m, s, ss) = rtc.datetime()        # Update RTC variables
    return (yyyy, mm, dd, wd, h, m, s, ss)                  # Return RTC variables
    
def get_datetime_string(rtc):
    (yyyy, mm, dd, wd, hh, m, s, ss) = rtc.datetime()       # Update RTC variables
    if hh >= 13:
        h = hh-12
        am_pm = "PM"
    else:
        h = hh
        am_pm = "AM"
    return (f"{mm}-{dd}-{yyyy} {h}:{m:02}:{s:02} {am_pm}")  # Return RTC variables as formatted string

def check_wifi(cmd):                                                                       
    wlan = network.WLAN(network.STA_IF)   
    ip_config = wlan.ifconfig() 

    count = 0
    if cmd == "check":                                     # Check wifi. 
        while count < 5 and wlan.isconnected() == False:   # Check, at most, 5 times over half a second if wifi is connected
            time.sleep_ms(100)
            count += 1
        if count >= 5 and wlan.isconnected() == False:
            reset()                                         # if not connected, reboot ESP32 to reconnect to Wifi
        else:
            return                                          # return if wifi OK
    
    elif cmd == "get":                                      # Get IP address
        return ip_config[0]                                 # Return the IP address

    
def send_email(rtc, email_subject):
    # Email details
    sender_email = "cadehouse419@gmail.com"
    sender_name = "Cade's Home" 
    recipient_email ="b_cade04@hotmail.com"
    sender_password = GOOGLE_PASSWORD
    email_body_1 = "Status: Smoke Detectors Online"
    timestamp = get_datetime_string(rtc)
    ip = check_wifi("get")

    if email_subject == 1:
        email_subject = "Bootup: Successfull"
        email_body_2 = "The ESP32 has successfully rebooted."
    elif email_subject == 2:
        email_subject = "NTP Clock Sync: Failed"
        email_body_2 = "The ESP32 clock sync failed. Retry will occur in 10 minutes."
    elif email_subject == 3:
        email_subject = "NTP Clock Sync: Successfull"
        email_body_2 = "The ESP32 has successfully synchronized it's clock with the NTP server."
    elif email_subject == 4:
        email_subject = "Input Tests: Successfull"
        email_body_2 = "The ESP32 utility power and smoke detector inputs are functioning properly."
    elif email_subject == 5:
        email_subject = "Input Tests - Smoke: Passed | Power: Failed"
        email_body_2 = "Utility power input test failed. Inspect ESP32 GPIO5 and relay."
    elif email_subject == 6:
        email_subject = "Input Tests - Smoke: Failed | Power: Passed"
        email_body_2 = "Smoke detector input test failed. Inspect ESP32 GPIO4 and relay."
    elif email_subject == 7:
        email_subject = "Input Tests: Failed"
        email_body_2 = "Circuit malfuntion. Both inputs failed self test. Inspect ESP32, circuit, and relays."
    elif email_subject == 8:
        email_subject = "SMOKE DETECTORS ACTIVATED!!"
        email_body_2 = "The smoke/carbon monoxide detectors are in alarm!"
    elif email_subject == 9:
        email_subject = "SMOKE DETECTORS NORMAL!!"
        email_body_2 = "The smoke/carbon monoxide detectors have returned to normal!"
    elif email_subject == 10:
        email_subject = "UTILITY POWER OFF!!"
        email_body_2 = "Utility power may be off or smoke detector circuit breaker tripped."
    elif email_subject == 11:
        email_subject = "UTILITY POWER RESTORED!!"
        email_body_2 = "Power has been restored to the smoke/carbon monoxide detectors."

    # Send the email
    smtp = umail.SMTP("smtp.gmail.com", 465, ssl=True)    # Gmail's SSL port
    smtp.login(sender_email, sender_password)
    smtp.to(recipient_email)
    smtp.write(f"From: {sender_name} <{sender_email}>\n")
    smtp.write(f"Subject: {email_subject} \n\n")
    smtp.write(f"{email_body_1} \n{timestamp} \n{ip}\n \n{email_body_2} \n")
    smtp.send()
    smtp.quit()

def debounce(pin, wdt):
    count = 0
    initial_state = pin.value()

    # 100 millisecond debounce
    while count < 10:                                  # check 10 times
        time.sleep_ms(10)                              # 10 ms between each check
        if pin.value() == initial_state:               # if the current input matches the initial status that triggered the debounce function...
            count += 1                                 # increment counter
        else:
            wdt.feed()                                 # reset WDT timer
            initial_state = pin.value()                # update the initial pin state
            count = 0                                  # reset counter if the state changes during debounce

    # after stable input state, return status
    if pin.value() == 1:    
        return True
    elif pin.value() == 0:
        return False



if __name__ == "__main__":
    main()