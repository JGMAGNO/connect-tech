import RPi.GPIO as GPIO
import time
import threading
import sys
import lcddriver
import pymysql
import serial
import serial.tools.list_ports
import adafruit_fingerprint

from time import sleep
from picamera import PiCamera
from sim800l import SIM800L
from flask import Flask, Response
from flask import render_template
from multiprocessing import Process, Value
from flask_cors import CORS
from threading import Thread

# creates a Flask application, named app
app = Flask(__name__)

stop_run = False
stop_threads = False
set_text_new = False
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
#db = pymysql.connect("localhost","mark","mark123","floodytech")
#cur = db.cursor()

# Fingerprint scanner setup
uart = serial.Serial(serial_port[0].device, baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

# GSM Module setup
sim800l = SIM800L('/dev/serial0')
sms_message = "Someone is trying to unlock the door"
dest="639569731165"


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
            print("Place finger on sensor...", end="", flush=True)
        else:
            print("Place same finger again...", end="", flush=True)

        while True:
            i = finger.get_image()
            if i == adafruit_fingerprint.OK:
                print("Image taken")
                break
            elif i == adafruit_fingerprint.NOFINGER:
                print(".", end="", flush=True)
            elif i == adafruit_fingerprint.IMAGEFAIL:
                print("Imaging error")
                return False
            else:
                print("Other error")
                return False

        print("Templating...", end="", flush=True)
        i = finger.image_2_tz(fingerimg)
        if i == adafruit_fingerprint.OK:
            print("Templated")
        else:
            if i == adafruit_fingerprint.IMAGEMESS:
                print("Image too messy")
            elif i == adafruit_fingerprint.FEATUREFAIL:
                print("Could not identify features")
            elif i == adafruit_fingerprint.INVALIDIMAGE:
                print("Image invalid")
            else:
                print("Other error")
            return False

        if fingerimg == 1:
            print("Remove finger")
            time.sleep(1)
            while i != adafruit_fingerprint.NOFINGER:
                i = finger.get_image()

    print("Creating model...", end="", flush=True)
    i = finger.create_model()
    if i == adafruit_fingerprint.OK:
        print("Created")
    else:
        if i == adafruit_fingerprint.ENROLLMISMATCH:
            print("Prints did not match")
        else:
            print("Other error")
        return False

    print("Storing model #%d..." % location, end="", flush=True)
    i = finger.store_model(location)
    if i == adafruit_fingerprint.OK:
        print("Stored")
    else:
        if i == adafruit_fingerprint.BADLOCATION:
            print("Bad storage location")
        elif i == adafruit_fingerprint.FLASHERR:
            print("Flash storage error")
        else:
            print("Other error")
        return False

    return True

def get_fingerprint():
    capture_data()
    lcd_clear()
    lcd_string("Waiting", 2) 
    lcd_string("for image.", 3) 
    sleep(1)
    lcd_clear()
    lcd_string("Waiting", 2) 
    lcd_string("for image..", 3) 
    sleep(1)
    lcd_clear()
    lcd_string("Waiting", 2) 
    lcd_string("for image...a", 3)     
    print("Waiting for image...")
    if set_text_new:
        lcd_clear()
        lcd_string("Please scan the", 2)
        lcd_string("fingerprint that", 3)
        lcd_string("you wish to delete", 4)
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
        if get_fingerprint():
            print("Detected #", finger.finger_id, "with confidence", finger.confidence, " ", finger.templates)
            global f_number
            f_number = len(finger.templates)
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
    global set_text_new
    stop_run = True
    stop_threads = True
    set_text_new = False
    return "Application stopped"

@app.route("/run", methods=['GET'])
def run_process():
    global stop_run
    global stop_threads
    global set_text_new
    stop_run = False
    stop_threads = False
    set_text_new = False
    return Response(manual_run(), mimetype="text/html")

@app.route('/add_finger')
def add_finger():
    #enroll_finger(len(finger.templates) + 1)
    print(f_number)
    return("Nothing")


@app.route('/del_finger')
def del_finger():
    global stop_threads
    global set_text_new
    stop_threads = False
    set_text_new = True
    print(len(finger.templates))
    print("Please enter the fingerprint to be deleted")
    if get_fingerprint():
        finger.delete_model(finger.finger_id)
        print("Deleted")
    else:
        print("Failed to delete")
    return("Nothing")


@app.route('/capture_image')
def capture_data():
    camera = PiCamera()
    camera.rotation = 180
    camera.resolution = (640,480)
    camera.framerate = 24    
    global i
    #print(i)    
    i = i + 1
    #print("Capturing Image")
    camera.capture('/var/www/html/images_cap/image_%s.jpg' % i)
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

@app.route('/lock')
def d_lock():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(channel, GPIO.OUT)
    GPIO.output(channel, GPIO.HIGH)    
    GPIO.cleanup()
    lcd_clear()
    lcd_string("Locked!", 2)
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
    return dest

@app.route('/setcp/<name>')
def set_cp(name):
    global dest
    dest = name
    return dest

@app.route("/")
def index_page():
    return render_template('index.html')

# run the application
if __name__ == "__main__":
    #p = Process(target=bg_loop)
    #p.start()
    app.run(debug=True, port=9977, host='0.0.0.0', threaded=True, use_reloader=False)      
    #p.join()  
