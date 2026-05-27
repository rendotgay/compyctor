# <img src="logo.ico" width="32" height="32"> Compyctor
A basic GUI for starting several Python scripts at once.

If you're anything like me, 
you've probably written countless Python scripts for various purposes, 
and need an easy way to start them every time you boot up your computer. 
Tabs in the terminal help, 
but it doesn't let me hide the window entirely. 
Plus, I'm not sure if you can automate starting terminals in tabs automatically, 
so I wrote this.

## Features
- Custom list of scripts
- Auto-start scripts
- View terminal output
- Auto update
- Minimize to tray
- Windows Toast notifications on errors
- Dark / Light themes

## Installation
Download the [latest release](https://github.com/rendotgay/compyctor/releases) or
```bash
git clone https://github.com/rendotgay/compyctor.git
cd compyctor
pip install -r requirements.txt
python gui.py
```

## Usage
1. Select `+ Add Script`
2. Select the python script you want to run
3. Set a name, arguments, or custom working directory and python directory if desired, as well as whether or not to auto-start
4. Click `Save`
5. Click `▶` to start the script
6. Click `⏹` to stop the script
7. Click `📄` to view the terminal output
8. Click `🗘` to restart the script
9. Click `🗑` to delete the script
10. Close the window to minimize to tray
