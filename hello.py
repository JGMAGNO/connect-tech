# serve.py
import os
from flask import Flask
from flask import render_template

# creates a Flask application, named app
app = Flask(__name__)
# a route where we will display a welcome message via an HTML template

@app.before_request
def before_request_func():
    print("before_request is running!")   

@app.route("/")
def hello():
    message = "Hello, World"
    return render_template('index.html', message=message)
    print("2") 

@app.route('/background_process_test')
def background_process_test():
    print("Hello")
    return("nothing")

@app.route('/background_process_test2')
def background_process_test2():
    print("Hello2")
    return("nothing") 

           

# run the application
if __name__ == "__main__":
    app.run(debug=True, port=6000, host='0.0.0.0')