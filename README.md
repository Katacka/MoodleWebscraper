# UPMoodleWebscraper

Webscraper utility purposed to retrieve all assignment and course resources for a given University of Portland student

## Ubuntu 16.04 Setup

Assuming Python 3 has been installed
* Install Selenium
  * _pip install -U selenium_
* Install Chrome/Chromium
  * _sudo curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add_\
    _sudo echo "deb https://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list_\
    _sudo apt-get -y update_\
    _sudo apt-get -y install google-chrome-stable_
* Install ChromeDriver
  * _wget -N https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip -P ~/_\
    _unzip ~/chromedriver_linux64.zip -d ~/_\
    _rm ~/chromedriver_linux64.zip_\
    _sudo mv -f ~/chromedriver /usr/local/bin/chromedriver_\
    _sudo chown root:root /usr/local/bin/chromedriver_\
    _sudo chmod 0755 /usr/local/bin/chromedriver_\
    
# Execution

Run _python scraper.py <moodle_username> <moodle_password>_
    
