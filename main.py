import RPi.GPIO as GPIO
import time
import threading
import sys
import lcddriver
import pymysql
import serial
import serial.tools.list_ports
import adafruit_fingerprint
import os
import shutil

from time import sleep
from picamera import PiCamera
from sim800l import SIM800L
from flask import Flask, Response, redirect
from flask import render_template
from multiprocessing import Process, Value
from flask_cors import CORS
from threading import Thread
from flask_socketio import SocketIO, emit
from twilio.rest import Client


account_sid = 'AC843d0bf8d98cb4c7164c8c1c8816b852'
auth_token = '46a5d14756c8e1c01a25feb773a6d71b'

client = Client(account_sid, auth_token)

body = "Someone is forcing to open the door"
from_ = '+15109240286'
to_ = '+639267322931' # please change this when changing phone number on twilio dashboard

folder = '/var/www/html/images_cap/images'
for filename in os.listdir(folder):
    file_path = os.path.join(folder, filename)
    try:
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.unlink(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
    except Exception as e:
        print('Failed to delete %s. Reason: %s' % (file_path, e))

# creates a Flask application, named app
app = Flask(__name__)
CORS(app)

stop_run = False
stop_threads = False
set_text_del = False
set_text_add = False
# Digital pin for the relay
channel = 21

# Variable for filaname counter
i = 0

# Variable for sms alert counter
j = 0

f_number = 0

# Piece of code for identifying usb serial
serial_port = list(serial.tools.list_ports.comports())

# LCD setup
lcd = lcddriver.lcd()
lcd.lcd_clear()

# Database setup
#db = pymysql.connect("","","","")
#cur = db.cursor()

# Fingerprint scanner setup
uart = serial.Serial(serial_port[0].device, baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

# GSM Module setup

# Functions

def lcd_clear():
    lcd.lcd_clear()

def lights_off():
    lcd.lcd_backlight("OFF")

def lights_on():
    lcd.lcd_backlight("ON")

def unlock(pin):
    GPIO.output(pin, GPIO.HIGH)

def lock(pin):
    GPIO.output(pin, GPIO.LOW)

def lcd_string(text, row):
    lcd.lcd_display_string(text, row)

def write_file(data, filename):
    # Convert binary data to proper format and write it on Hard Disk
    with open(filename, 'wb') as file:
        file.write(data)

def convertToBinaryData(filename):
    # Convert digital data to binary format
    with open(filename, 'rb') as file:
        binaryData = file.read()
    return binaryData

def insertBLOB(emp_id, photo, video):
    print("Inserting BLOB")
    try:
        db = pymysql.connect("localhost","mark","mark123","connectech")
        cursor = db.cursor()
        sql_insert_blob_query = """INSERT INTO Python_Employee(id, photo, video) VALUES (%s,%s,%s)"""
        empPicture = convertToBinaryData(photo)
        empVideo = convertToBinaryData(video)
        insert_blob_tuple = (emp_id, empPicture, empVideo)
        cursor.execute(sql_insert_blob_query, insert_blob_tuple)
        db.commit()
        print("Inserted successfully")
    except TypeError as e:
        print(e)

def readBLOB(emp_id, photo, video):
    print("Reading BLOB")
    try:
        db = pymysql.connect("localhost","mark","mark123","connectech")
        cursor = db.cursor()
        sql_fetch_blob_query = """SELECT * from Python_Employee where id = %s"""
        cursor.execute(sql_fetch_blob_query, (emp_id,))
        record = cursor.fetchall()
        for row in record:
            print("Id = ", row[0], )
            image = row[1]
            vid = row[2]
            print("Storing employee image and bio-data on disk \n")
            write_file(image, photo)
            write_file(vid, video)
    except TypeError as e:
        print(e)

def enroll_finger(location):
    """Take a 2 finger images and template it, then store in 'location'"""
    for fingerimg in range(1, 3):
        if fingerimg == 1:
            #print("Place finger on sensor...", end="", flush=True)
            lcd_clear()
            lcd_string("Place finger", 1)
            lcd_string("on sensor", 2)
        else:
            #print("Place same finger again...", end="", flush=True)
            lcd_clear()
            lcd_string("Place same", 1)
            lcd_string("finger again", 2)

        while True:
            i = finger.get_image()
            if i == adafruit_fingerprint.OK:
                #print("Image taken")
                
                lcd_string("Image taken!", 4)
                break
            elif i == adafruit_fingerprint.NOFINGER:
                #print(".", end="", flush=True)
                print("")
            elif i == adafruit_fingerprint.IMAGEFAIL:
                #print("Imaging error")
                lcd_string("Imaging Error!", 4)
                return False
            else:
                #print("Other error")
                lcd_string("Other error!", 4)
                return False

        #print("Templating...", end="", flush=True)
        lcd_clear()
        lcd_string("Templating...", 1)
        i = finger.image_2_tz(fingerimg)
        if i == adafruit_fingerprint.OK:
            #print("Templated")
            lcd_string("Templated", 3)
        else:
            if i == adafruit_fingerprint.IMAGEMESS:
                #print("Image too messy")
                lcd_string("Image too messy", 3)
            elif i == adafruit_fingerprint.FEATUREFAIL:
                #print("Could not identify features")
                lcd_string("Could not", 3)
                lcd_string("identify features", 4)
            elif i == adafruit_fingerprint.INVALIDIMAGE:
                #print("Image invalid")
                lcd_string("Image invalid", 3)
            else:
                #print("Other error")
                lcd_string("Other error", 3)
            return False

        if fingerimg == 1:
            print("Remove finger")
            time.sleep(1)
            while i != adafruit_fingerprint.NOFINGER:
                i = finger.get_image()

    #print("Creating model...", end="", flush=True)
    lcd_clear()
    lcd_string("Creating model...", 1)    
    i = finger.create_model()
    if i == adafruit_fingerprint.OK:
        #print("Created")
        lcd_string("Created", 2)
    else:
        if i == adafruit_fingerprint.ENROLLMISMATCH:
            #print("Prints did not match")
            lcd_string("Prints did not match", 2)
        else:
            #print("Other error")
            lcd_string("Other error", 2)
        return False

    #print("Storing model #%d..." % location, end="", flush=True)
    lcd_string("Storing model...", 3)
    i = finger.store_model(location)
    if i == adafruit_fingerprint.OK:
        #print("Stored")
        lcd_string("Stored", 4)
    else:
        if i == adafruit_fingerprint.BADLOCATION:
            #print("Bad storage location")
            lcd_string("Bad storage location", 4)
        elif i == adafruit_fingerprint.FLASHERR:
            #print("Flash storage error")
            lcd_string("Flash storage error", 4)
        else:
            #print("Other error")
            lcd_string("Other error", 4)
        return False

    return True

def get_fingerprint():
    capture_data()
    lcd_clear()
    lcd_string("Waiting", 2) 
    lcd_string("for image.", 3)     
    print("Waiting for image...")
    if set_text_del:
        lcd_clear()
        lcd_string("Please scan the", 2)
        lcd_string("fingerprint that", 3)
        lcd_string("you wish to delete", 4)
    if set_text_add:
        lcd_clear()
        lcd_string("Please scan the", 2)
        lcd_string("fingerprint that", 3)
        lcd_string("you wish to add", 4)
    while finger.get_image() != adafruit_fingerprint.OK:
        global stop_threads
        if stop_threads:
            return False
        print("checker")
        pass
    print("Templating...")
    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        return False
    print("Searching...")
    if finger.finger_fast_search() != adafruit_fingerprint.OK:
        return False
    return True

def bg_loop():
    global j
    global stop_run
    while not stop_run:
        GPIO.cleanup()
        if finger.read_templates() != adafruit_fingerprint.OK:
            raise RuntimeError('Failed to read templates')  
        print("Fingerprint templates:", len(finger.templates))
        if get_fingerprint():
            print("Detected #", finger.finger_id, "with confidence", finger.confidence, " ", finger.templates)
            lcd_clear()
            lcd_string("Fingerprint", 2)
            lcd_string("found!", 3)
            sleep(1)
            lcd_clear()
            lcd_string("Opening!", 2)            
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(channel, GPIO.OUT)
            GPIO.output(channel, GPIO.HIGH)
            j = 0
            sleep(5)
        else:
            j = j + 1
            if j == 3:
                print("Overflow")
                # send an sms
                #sim800l.send_sms(dest,sms)
                message = client.messages \
                                .create(body=body,from_=from_,to=to_)
                lcd_clear()
                lcd_string("Alerting", 2)
                lcd_string("the owner!", 3)
                sleep(2)
                j = 0
            else:
                print("Continue")
            print(j)
            lcd_clear()
            lcd_string("Fingerprint", 2)
            lcd_string("not found!", 3)
            sleep(2) 

def manual_run():
    t = Thread(target=bg_loop)
    t.start()
    return("Processing")

# Flask routes

@app.route("/stop", methods=['GET'])
def set_stop_run():
    global stop_run
    global stop_threads
    global set_text_del
    global set_text_add
    stop_run = True
    stop_threads = True
    set_text_del = False
    set_text_add = False
    return "Application stopped"

@app.route("/run", methods=['GET'])
def run_process():
    global stop_run
    global stop_threads
    global set_text_del
    global set_text_add
    stop_run = False
    stop_threads = False
    set_text_del = False
    set_text_add = False
    return Response(manual_run(), mimetype="text/html")

@app.route('/add_finger')
def add_finger():
    set_stop_run()
    sleep(1)
    global stop_threads
    global set_text_del
    global set_text_add
    global f_number
    stop_threads = False
    set_text_del = False
    set_text_add = True
    if finger.read_templates() != adafruit_fingerprint.OK:
            raise RuntimeError('Failed to read templates')
    global f_number
    f_number = len(finger.templates)
    print("number: ",f_number)    
    print("Please scan the fingerprint to be add")
    print("Number of current enrolled: ",f_number)
    enroll_finger(f_number + 1)
    print("Fingerprint Added")
    sleep(1)
    run_process() 
    return("Nothing")


@app.route('/del_finger')
def del_finger():
    set_stop_run()
    sleep(1)
    global stop_threads
    global set_text_del
    global set_text_add
    stop_threads = False
    set_text_del = True
    set_text_add = False
    #print(len(finger.templates))
    print("Please enter the fingerprint to be deleted")
    if get_fingerprint():
        finger.delete_model(finger.finger_id)
        print("Deleted")
    else:
        print("Failed to delete")
    sleep(1)
    run_process()
    return("Nothing")


@app.route('/capture_image')
def capture_data():
    camera = PiCamera()
    camera.rotation = 45
    camera.resolution = (640,480)
    camera.framerate = 24 
    
    global i
    global timestr
    timestr = time.strftime("%b %d, %Y %H:%M %p ")   
    #print(i)    
    i = i + 1
    #print("Capturing Image")
    camera.capture('/var/www/html/images_cap/images/%s image_%d.jpg' % (timestr, i)) 
    #print("Saving Stream")
    #camera.start_recording('/home/pi/Desktop/connect-tech/videos/video_%s.h264' % i)
    #sleep(5)
    #camera.stop_recording()
    #print("Saving it to DB")
    #insertBLOB(i, '/home/pi/Desktop/connect-tech/images/image_%s.jpg' % i, '/home/pi/Desktop/connect-tech/videos/video_%s.h264' % i)
    #print("Reading it from DB")
    #readBLOB(i, '/home/pi/Desktop/connect-tech/output/images/image_%s.jpg' % i, '/home/pi/Desktop/connect-tech/output/videos/video_%s.h264' % i)
    #sleep(1)
    camera.close()
    return("Nothing")

@app.route('/start_stream')
def start_stream():
    return("Nothing")

@app.route('/stop_stream')
def stop_stream():
    return("Nothing")

@app.route('/lock')
def d_lock():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(channel, GPIO.OUT)
    GPIO.output(channel, GPIO.HIGH)    
    GPIO.cleanup()
    lcd_clear()
    lcd_string("Locked!", 2)
    #emit('update value')
    return("Nothing")

@app.route('/unlock')
def d_unlock():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(channel, GPIO.OUT)
    GPIO.output(channel, GPIO.LOW)
    lcd_clear()
    lcd_string("Unlocked!", 2)
    return("Nothing")

@app.route('/returncp')
def return_cp():
    return to_[1:]

@app.route('/setcp/<name>')
def set_cp(name):
    print(name)
    global to_
    to_ = name
    return to_

@app.route("/", methods=['GET'])
def index_page():
    #return redirect("static/control.html", code=302)
    run_process()
    return render_template('index.html')

# run the application
if __name__ == "__main__":
    #p = Process(target=bg_loop)
    #p.start()
    app.run(debug=True, port=81, host='0.0.0.0', threaded=True, use_reloader=False)   
    #socketio.run(app)   
    #p.join()  