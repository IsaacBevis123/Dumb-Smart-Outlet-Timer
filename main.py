# The Dumb-Smart Outlet Timer
# Author Isaac Bevis

import time
import ntptime
import network
import socket
import _thread
from machine import Pin

status_led = Pin(6, Pin.OUT)
error_led = Pin(22, Pin.OUT)
relay = Pin(13, Pin.OUT)
relay_state = 'Relay State Unknown'

ssid = "you wifi ssid"
password = 'your wifi password'

TIME_ZONE = 0 # Universal Time
UTC_OFFSET = TIME_ZONE * 60 * 60
TURN_ON_TIME = [12, 0]
TURN_OFF_TIME = [12, 0]

interrupt_wait = True
restart_thread = True

temporary_data = []
use_temp_data = False

set_ntp_time = False

wlan = network.WLAN(network.STA_IF)


## Time Keeping Functions ##
# Function thread 1
# Runs on core 1 of RP2040
# Handles waiting until next action (relay off or on) or interupted by main core
def thread_1():
    is_waiting = False
    sleep_time = 0
    global TURN_ON_TIME
    global TURN_OFF_TIME
    while True:
        if not is_waiting:
            actual_time = time.localtime(time.time() + UTC_OFFSET)
            turn_on_time = convert_time(TURN_ON_TIME)
            turn_off_time = convert_time(TURN_OFF_TIME)
            # if next action is turn on
            if turn_on_time < turn_off_time:
                print("next action turn on...")
                # make sure relay is off
                if relay.value() != 0:
                    turn_off()
                
                sleep_time = time_diff(actual_time, turn_on_time)
                print("sleeping until " + str(turn_on_time) + " (" + str(sleep_time) + " seconds)")
                is_waiting = True
                #time.sleep(sleep_time)
            
            # if next action is turn off
            elif turn_off_time < turn_on_time:
                print("next action turn off...")
                # make sure relay is on
                if relay.value() != 1:
                    turn_on()
                
                sleep_time = time_diff(actual_time, turn_off_time)
                print("sleeping until " + str(turn_off_time) + " (" + str(sleep_time) + " seconds)")
                is_waiting = True
                #time.sleep(sleep_time)
            
        
        else: # if is_waiting
            global interrupt_wait
            if interrupt_wait:
                print("interrupt recieved")
                global restart_thread
                restart_thread = True
                return
                
            elif sleep_time > 0:
                sleep_time -= 1
                time.sleep(1)
                
            elif sleep_time == 0:
                is_waiting = False
                print("wakeing up")


## Networking Functions ##
# Function serve client
# Recieves incoming http requests and sends http response
def serve_client():
    try: 
        cl, addr = s.accept()
        print('client connected from', addr)
        request = cl.recv(1024)
        print("request:")
        print(request)
        request = str(request)
        
        if request.find('?') == 7:
            handle_client_request(request)
        
        # Create and send response
        reponse = get_response()
        
        cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        cl.send(reponse)
        cl.close()
    
    except OSError as e:
        with open("error.html", "r") as f:
            html = f.read()
        
        response = html % e
        cl.send('HTTP/1.0 500 \r\nContent-type: text/html\r\n\r\n')
        cl.send(response)
        cl.close()
        print("Error: " + e)

# function add times
# assume time1 and time2 are length 8 tuples (same as output of time.localtime())
# adds time 1 to time 2 with roll over
def add_times(time1, time2):
    # convert times to seconds since 1970
    sec1 = time.mktime(time1)
    sec2 = time.mktime(time2)
    
    # add the times in seconds together
    sec = sec1 + sec2
        
    # convert back to standerd notation 
    return time.localtime(sec)

# function time diff
# assume time1 and time2 are length 8 tuples
# returns the difference in seconds from time1 to time2
def time_diff(time1, time2):
    # convert times to seconds since 1970
    sec1 = time.mktime(time1)
    sec2 = time.mktime(time2)
    
    # subtract to find diff
    sec = sec2 - sec1
    
    return sec

# function convert time
# converts user input [hour, min] to 8 length tuple
# assume t is list of length 2
def convert_time(t):
    at = time.localtime(time.time() + UTC_OFFSET)
    # time is in the future of now
    if t[0] > at[3]:
        usr_sec = time.mktime((at[0], at[1], at[2], t[0], t[1], 0, at[6], at[7]))
        return time.localtime(usr_sec)
    elif t[0] == at[3] and t[1] > at[4]:
        usr_sec = time.mktime((at[0], at[1], at[2], t[0], t[1], 0, at[6], at[7]))
        return time.localtime(usr_sec)
    
    # time is in the past (assume next day)
    new_at = add_times(at, time.localtime(24*60*60))
    usr_sec = time.mktime((new_at[0], new_at[1], new_at[2], t[0], t[1], 0, new_at[6], new_at[7]))
    return time.localtime(usr_sec)

# function save data
# saves the current timezone, turnon, and turnoff times to a file named data.json on the raspberry pi pico
def save_data():
    with open("data.json", "w") as f:
        f.write("timezone=" + str(TIME_ZONE) + "\n")
        f.write("turnon_time=" + str(TURN_ON_TIME[0]) + ":" + str(TURN_ON_TIME[1]) + "\n")
        f.write("turnoff_time=" + str(TURN_OFF_TIME[0]) + ":" + str(TURN_OFF_TIME[1]) + "\n")

# function load data
# sets global flag notifying response to use temp data in http response
# loads data from data.json into temp data
# 		done this way so that user can see data parameters before applying
def load_data():
    with open("data.json", "r") as f:
        data = f.read()
    
    parsed_data = data.split("\n")
    print("parsed data: " + str(parsed_data))
    tmp_timezone = parsed_data[0].split("=")
    tmp_turnon_time = parsed_data[1].split("=")[1].split(":")
    tmp_turnoff_time = parsed_data[2].split("=")[1].split(":")
    
    global temporary_data
    temporary_data.append(int(tmp_timezone[1]))
    temporary_data.append([int(tmp_turnon_time[0]), int(tmp_turnon_time[1])])
    temporary_data.append([int(tmp_turnoff_time[0]), int(tmp_turnoff_time[1])])
    
    global use_temp_data
    use_temp_data = True


# Function handle client request
# Parses the URL query string
# Handles each query request
def handle_client_request(request):
    actual_time = time.localtime(time.time() + UTC_OFFSET)
    
    request = request.replace('?', ' ')
    split_req = request.split(' ')
    str_vars = split_req[2]
    
    list_vars = str_vars.split('&')
    print("req_vars: " + str(list_vars))
    
    for req in list_vars:
        
        # Handle set timezone
        if 'timezone=' in req:
            timezone = req.split('=')
            global TIME_ZONE
            TIME_ZONE = int(timezone[1])
    
        # Handle set turn on time request
        elif 'turnon_time=' in req:
            turnon_time = req.split('=')
            on_time = turnon_time[1].replace("%3A", " ")
            on_time = on_time.split(' ')
            
            global TURN_ON_TIME
            TURN_ON_TIME = [int(on_time[0]), int(on_time[1])]
            
            print("New turn on time: " + str(TURN_ON_TIME))
        
    
        # Handle set turn off time request
        elif 'turnoff_time=' in req:
            turnoff_time = req.split('=')
            off_time = turnoff_time[1].replace("%3A", " ")
            off_time = off_time.split(' ')
            
            global TURN_OFF_TIME
            TURN_OFF_TIME = [int(off_time[0]), int(off_time[1])]
            
            print("New turn off time: " + str(TURN_OFF_TIME))
        
        # handle submit new info
        elif 'submit=' in req:
            submit = req.split('=')
            if submit[1] == "submit":
                # interrupt thread 1 and restart with new data
                global interrupt_wait
                interrupt_wait = True
                print("sent interrupt in handle client request...")
            elif submit[1] == "save":
                # save settings to persistant storage
                save_data()
            elif submit[1] == "load":
                # load settings from persistant storage
                load_data()
                
        
        # Handle reload request
        elif 'reload=true' in req:
            reload_time()
    
        # Handle relay request
        elif 'relay=on' in req:
            turn_on()
        elif 'relay=off' in req:
            turn_off()
        
# Function turn on
# turns on relay and relay status led
def turn_on():
    global relay_state
    relay_state = "ON"
    print("Relay on")
    status_led.value(1)
    relay.value(1)

# Function turn off
# turns off relay and relay status led
def turn_off():
    global relay_state
    relay_state = "OFF"
    print("Relay off")
    status_led.value(0)
    relay.value(0)

# Function reload time
# tries to set ntp time
# changes set_ntp_time flag to True if successful
def reload_time():
    ntp_tries = 3
    while True:
        try:
            print("trying to get ntp time...")
            ntptime.settime()
            break
        except OSError as e:
            ntp_tries -= 1
            if ntp_tries == 0:
                show_error(4, 2)
                return
        time.sleep(0.2)
    
    global set_ntp_time
    set_ntp_time = True

# Function get time
# returns current system time in 12 hr format
def get_time():
    # Set UTC_OFFSET in case user changed timezone
    global UTC_OFFSET
    UTC_OFFSET = TIME_ZONE * 60 * 60
    
    actual_time = time.localtime(time.time() + UTC_OFFSET)
    print("Local time: " + str(actual_time))
    
    formatted_time = ""
    hrs = 12 if actual_time[3] == 0 else (actual_time[3] if actual_time[3] < 12 else actual_time[3] % 12)
    str_min = "0" + str(actual_time[4]) if actual_time[4] < 10 else str(actual_time[4])
    str_sec = "0" + str(actual_time[5]) if actual_time[5] < 10 else str(actual_time[5])
    mark = "AM" if actual_time[3] < 12 else "PM"
    
    formatted_time = "%s:%s:%s %s  %s/%s/%s" % (str(hrs), str_min, str_sec, mark, actual_time[1], actual_time[2], actual_time[0])
    
    return formatted_time

# function get on time
# returns the turn on time in 24hr format
def get_on_time():
    if use_temp_data:
        hour = ("%s" if temporary_data[1][0] >= 10 else "0%s") % temporary_data[1][0]
        minute = ("%s" if temporary_data[1][1] >= 10 else "0%s") % temporary_data[1][1]
    else:
        hour = ("%s" if TURN_ON_TIME[0] >= 10 else "0%s") % TURN_ON_TIME[0]
        minute = ("%s" if TURN_ON_TIME[1] >= 10 else "0%s") % TURN_ON_TIME[1]
    return "%s:%s" % (hour, minute)

# Function get off time
# returns the turn off time in 24hr format
def get_off_time():
    if use_temp_data:
        hour = ("%s" if temporary_data[2][0] >= 10 else "0%s") % temporary_data[2][0]
        minute = ("%s" if temporary_data[2][1] >= 10 else "0%s") % temporary_data[2][1]
    else:
        hour = ("%s" if TURN_OFF_TIME[0] >= 10 else "0%s") % TURN_OFF_TIME[0]
        minute = ("%s" if TURN_OFF_TIME[1] >= 10 else "0%s") % TURN_OFF_TIME[1]
    return "%s:%s" % (hour, minute)


# function get selected timezone
# return a list of length 27 of empty strings with "selected" in spot corresponding to selected timezone in html file
def get_selected_timezone():
    lt = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
    if use_temp_data:
        lt[temporary_data[0]+12] = "selected"
        
    else:
        lt[TIME_ZONE+12] = "selected"
        
    return lt

# function get response
# reads index.html and replaces %s with current info
# returns new html string
def get_response():
    with open("index.html", "r") as f:
        html = f.read()
    
    formatted_time = get_time()
    
    ltz = get_selected_timezone()
    
    time_correct_info = "" if set_ntp_time else "Unable to set NTP Time!"
    time_correct_button = "#4CAF50" if set_ntp_time else "#D11D53"
    
    val = html % (time_correct_button, time_correct_info, formatted_time, relay_state, ltz[0], ltz[1], ltz[2], ltz[3], ltz[4], ltz[5], ltz[6], ltz[7], ltz[8], ltz[9], ltz[10], ltz[11], ltz[12], ltz[13], ltz[14], ltz[15], ltz[16], ltz[17], ltz[18], ltz[19], ltz[20], ltz[21], ltz[22], ltz[23], ltz[24], ltz[25], ltz[26], get_on_time(), get_off_time())
    
    # reset use_temp_data flag
    global use_temp_data
    global temporary_data
    if use_temp_data:
        temporary_data = []
        use_temp_data = False
    
    return val

# Function show error
# flashes error led a number of times equal to code/2 then pauses for 2 seconds
# ends after repeating this t times
def show_error(code, t):
    error_led.value(0)
    flash_count = 0
    nt = t
    while True:
        error_led.toggle()
        flash_count += 1
        if flash_count == code:
            flash_count = 0
            time.sleep(2)
            nt -= 1
            if nt == 0:
                return
        else:
            time.sleep(0.3)


## Main Program ##
# Light error_led to show connection in progress
error_led.value(1)

wlan.active(True)
wlan.connect(ssid, password)

# Wait for connect or fail
max_wait = 20
while max_wait > 0:
    print(wlan.status())
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    print('waiting for connection...')
    time.sleep(1)
    
# Handle connection error
if wlan.status() != 3:
    print(wlan.status())
    show_error(8, 999)
else:
    print('Connected')
    status = wlan.ifconfig()
    print( 'ip = ' + status[0] )
    
    
    
# Open socket
try:
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    print('listening on', addr)
except OSError as e:
    show_error(6, 999)

reload_time()

actual_time = time.localtime(time.time() + UTC_OFFSET)
print("Local time: " + str(actual_time))

# Turn off error led to show connection finished
error_led.value(0)

# Listen for connections, serve client
while True:
    if restart_thread:
        print("starting second thread...")
        # Start second thread
        interrupt_wait = False
        restart_thread = False
        _thread.start_new_thread(thread_1, ())
    
    elif not interrupt_wait:
        serve_client()
            
        
    
    

