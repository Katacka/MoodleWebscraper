from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import InvalidArgumentException, NoSuchElementException, ElementNotVisibleException, NoAlertPresentException
import sys
import time
import os
import pickle #TODO - Remove
import string
import re
import urllib.request
import shutil

class Course():
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.file_groups = {}
        self.html = None

## Helper Methods ##

def setupDriver(load_speed):
    #Ensure directory for downloaded files exists
    if not os.path.isdir("files"):
        os.mkdir("files")
        
    #Create browser web driver
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    options.add_argument('--headless')
    options.add_argument('--disable-extensions')
    options.add_argument('--safebrowsing-disable-extension-blacklist')
    options.add_argument('--safebrowsing-disable-download-protection')
    prefs = {"download.default_directory": os.path.dirname(os.path.abspath(__file__)) + "/files",
             'download.prompt_for_download': False,
             'safebrowsing.enabled': True,
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(chrome_options=options)
    driver.implicitly_wait(load_speed)
    return driver


def queryMoodle(driver):
    url = "https://learning.up.edu/moodle"
    visitPage(driver, url)


def loginMoodle(driver, load_speed):
    #Login if necessary
    try:
        #Enter email/username
        email_input = driver.find_element_by_id("i0116")
        email_input.send_keys(sys.argv[1])
        driver.find_element_by_id("idSIButton9").click()
        time.sleep(load_speed)

        #Enter password
        pass_input = driver.find_element_by_id("i0118")
        pass_input.send_keys(sys.argv[2])
        driver.find_element_by_id("idSIButton9").click()
        time.sleep(load_speed)

        #Navigate off login page
        driver.find_element_by_id("idSIButton9").click()
    
    except IndexError:
        print("ERROR: Improper CLI format\nPlease use: 'scraper.py <email@up.edu> <password>'");
        driver.quit()
        exit()
    
    except NoSuchElementException:
        pass #Login not required..? Debug with non-headless browser if errors propogate


def scrapeCourseMetadata(driver, load_speed):
    #Generate list of course meta-data
    try:
        #Set course overview to display all courses
        driver.find_element_by_id("groupingdropdown").click()
        course_overview = driver.find_element_by_id("inst279425")
        course_overview.find_element_by_xpath(".//a[@data-value='all']").click()

        #Scrape course meta-data
        course_dict = {}
        while (True):
            course_overview = driver.find_element_by_id("inst279425")        
            courses = course_overview.find_elements_by_class_name("coursename")
            course_dict = getCourseDict(courses, course_dict)
        
            next_page = course_overview.find_element_by_xpath(".//li[@data-control='next']")
            if (next_page.get_attribute("aria-disabled") == "true"):
                break

            next_page.click()
            time.sleep(load_speed)

    except NoSuchElementException:
        print("ERROR: Unexpected course overview format\n")
        driver.quit()
        exit()

    return course_dict


def getCourseDict(courses, course_dict):
    for course in courses:
        if not course.text:
            continue
        
        course_name = formatCourseName(course.text)
        course_dict[course_name] = Course(course_name, course.get_attribute("href"))
    return course_dict


def downloadCourseData(driver, course_dict):
    #Traverse courses
    for course_name in course_dict:
        try:
            #Visit course page
            course = course_dict[course_name]
            visitPage(driver, course.url)
        
            #Traverse course file groups
            assignments = driver.find_elements_by_class_name("assign")
            resources = driver.find_elements_by_class_name("resource")

            assignment_files = scrapeAssignments(assignments)
            resource_files = scrapeResources(resources)

            #Update course data
            course = downloadAssignments(driver, course, assignment_files)
            course_dict[course_name] = downloadResources(driver, course, resource_files)

        except NoSuchElementException:
            print("ERROR: Unexpected course assignment format\n")
            driver.quit()
            exit()

    return course_dict
    

def scrapeAssignments(files):
    file_names = [f.find_element_by_xpath(".//span[@class='instancename']").text
                  for f in files]
    file_urls = [f.find_element_by_xpath(".//a").get_attribute("href") for f in files]
    return zip(file_names, file_urls)

def downloadAssignments(driver, course, assignments):
    for assign_name, assign_url in assignments:
        assign_name = formatDefault(assign_name)
                
        visitPage(driver, assign_url)
        course.html = driver.page_source
                
        #Download files
        displayHiddenFiles(driver)
        downloads = driver.find_elements_by_xpath("//div[@class='fileuploadsubmission']/a")

        download_names = [d.text for d in downloads]
        download_urls = [d.get_attribute("href") for d in downloads]
        
        if len(downloads) > 0:
            course.file_groups[assign_name] = []
            for download_name, url in zip(download_names, download_urls):
                name = downloadUrl(url, formatDefault(download_name))
                course.file_groups[assign_name].append(name)

    return course


def displayHiddenFiles(driver):
    #Show hidden files
    expandIcons = driver.find_elements_by_xpath("//a[@aria-expanded='false']")
    for icon in expandIcons:
        try:
            icon.click()
            
        except ElementNotVisibleException:
            continue #Skip element


def scrapeResources(files):
    file_names = [f.find_element_by_xpath(".//span[@class='instancename']").text
                  for f in files]
    file_urls = [f.find_element_by_xpath(".//a").get_attribute("href") for f in files]
    return zip(file_names, file_urls)


def downloadResources(driver, course, resources):        
    for resource_name, resource_url in resources:
        resource_name = formatDefault(resource_name)

        name = downloadUrl(resource_url, resource_name)
        course.file_groups[name] = name

    return course


def downloadUrl(url, file_name, max_attempts=64):
    allDownloadsFinished()
    with urllib.request.urlopen(url) as response:
        name = file_name
        for i in range(1, max_attempts):
            try:
                shutil.copyfileobj(response, open("files/" + name, 'wb'))
                return name
            except FileExistsError:
                name = file_name + " (" + i + ")"
        return file_name

                
def visitPage(driver, url):
    try:
        #Wait for all previous downloads to finish
        allDownloadsFinished()
        driver.get(url)

    except InvalidArgumentException:
        print("ERROR: Malformed URL: ", url)
        driver.quit()
        exit()

        
def allDownloadsFinished():
    while (True):
        finished = True
        for i in os.listdir("files/"):
            if ".crdownload" in i:
                finished = False
                time.sleep(0.5)
                
        if finished:
            break
        

def formatCourseName(text):
    if "-" in text:
        text = text.rpartition("-")[-1].strip()
    if "\n" in text:
        text = text.rpartition("\n")[-1].strip()
    return formatDefault(text)


def formatDefault(text):
    text = removeNonPrintable(text)
    if "\n" in text:
        text = text.rpartition("\n")[0]
    return text.replace("/", " ").replace("?", " ").replace("*", " ").strip()


def removeNonPrintable(text):
    printable = set(string.printable)
    return ''.join(filter(lambda x: x in printable, text))
        

def organizeFiles(courses, file_root):
    allDownloadsFinished()
    for course_name in courses:
        course = courses[course_name]

        #Create sub-folder for course
        if len(course.file_groups) > 0:
            course_path = file_root + course_name +"/"
            if not os.path.isdir(course_path):
                os.mkdir(course_path)

                if course.html:
                    f = open(course_path + course_name + ".html", "w")
                    f.write(course.html)
                    f.close()
        
            for group_name in course.file_groups:
                file_group = course.file_groups[group_name]
                
                if not isinstance(file_group, list):
                    moveFile(file_group, file_root, course_path)
                
                elif len(file_group) > 0:
                    group_path = course_path + group_name + "/"
                    if not os.path.isdir(group_path):
                        os.mkdir(group_path)

                    for file_name in file_group:
                        moveFile(file_name, file_root, group_path)

                        
def moveFile(file_name, file_root, group_path):
    try:
        os.rename(file_root + file_name, group_path + file_name)
    except FileNotFoundError:
        file_name += "( \([0-9]+\))?"
        
        for f_name in os.listdir(file_root):
            if re.match(file_name, f_name):
                os.rename(file_root + f_name, group_path + f_name)

                        
## Main ##

#Create driver and access Moodle
driver = setupDriver(5)
queryMoodle(driver)
loginMoodle(driver, 1)

#Visit each course and download all relevant files
courses = scrapeCourseMetadata(driver, 1)
courses = downloadCourseData(driver, courses)

#TODO - Delete
pickle.dump(courses, open("courses", "wb"))
#courses = pickle.load(open("courses", "rb"))

#Re-organize files
organizeFiles(courses, "files/")

