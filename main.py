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
from flask import Flask
from flask import render_template
from multiprocessing import Process, Value

# creates a Flask application, named app
app = Flask(__name__)


# Digital pin for the relay
channel = 21

# Variable for filaname counter
i = 0

# Variable for sms alert counter
j = 0

# Piece of code for identifying usb serial
serial_port = list(serial.tools.list_ports.comports())

# LCD setup
lcd = lcddriver.lcd()
lcd.lcd_clear()

# Database setup
db = pymysql.connect("localhost","mark","mark123","floodytech")
cur = db.cursor()

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

def get_fingerprint():
    capture_data()
    print(i)
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
    lcd_string("for image...", 3)     
    print("Waiting for image...")
    while finger.get_image() != adafruit_fingerprint.OK:
        pass
    print("Templating...")
    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        return False
    print("Searching...")
    if finger.finger_fast_search() != adafruit_fingerprint.OK:
        #seconds = round(count.finish())
        #print("You took {} seconds between Enter actions".format(seconds))
        return False
    return True

def bg_loop():
    global j
    while True:
        GPIO.cleanup()
        if get_fingerprint():
            print("Detected #", finger.finger_id, "with confidence", finger.confidence)
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

# Flask routes         

@app.route('/capture_image')
def capture_data():
    camera = PiCamera()
    camera.rotation = 180
    camera.resolution = (640,480)
    camera.framerate = 24    
    global i
    print(i)    
    i = i + 1
    #print("Capturing Image")
    camera.capture('/home/pi/Desktop/connect-tech/images/image_%s.jpg' % i)
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
    p = Process(target=bg_loop)
    p.start()
    app.run(debug=True, port=9977, host='0.0.0.0', threaded=True, use_reloader=False)      
    p.join()  