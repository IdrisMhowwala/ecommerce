"""run.py — Local development shortcut. Same as: python wsgi.py"""
from wsgi import app

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
