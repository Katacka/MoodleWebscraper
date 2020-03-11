import os
import re
import shutil
import string
import sys
import time
import urllib.request
from getpass import getpass
from typing import Dict, List, Tuple, Iterator

from selenium import webdriver
from selenium.common.exceptions import InvalidArgumentException, NoSuchElementException, ElementNotVisibleException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


class Course:
    def __init__(self, course_name: str, url: str):
        self.course_name = course_name
        self.url = url
        self.file_groups = {}
        self.html = None


# region Helper Methods

# Create a Selenium Chrome driver and configure options
def setup_chrome_web_driver(load_speed: int) -> WebDriver:
    # Ensure directory for downloaded files exists
    if not os.path.isdir("files"):
        os.mkdir("files")

    # Set web driver options
    options = webdriver.ChromeOptions()
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--incognito")
    options.add_argument("--headless")
    options.add_argument("--disable-extensions")
    options.add_argument("--safebrowsing-disable-extension-blacklist")
    options.add_argument("--safebrowsing-disable-download-protection")
    prefs = {
        "download.default_directory": os.path.dirname(os.path.abspath(__file__)) + "/files",
        "download.prompt_for_download": False,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)

    # Create web driver
    chrome_web_driver = webdriver.Chrome(chrome_options=options)
    chrome_web_driver.implicitly_wait(load_speed)
    return chrome_web_driver


# Attempt to visit the Moodle homepage
def query_moodle(web_driver: WebDriver) -> None:
    visit_page(web_driver, "https://learning.up.edu/moodle")


# Navigate through Moodle's login menus
def login_to_moodle(web_driver: WebDriver, load_speed: int) -> None:
    # Login if necessary
    try:
        email_input = web_driver.find_element_by_id("i0116")
        pass_input = web_driver.find_element_by_id("i0118")
    except NoSuchElementException:
        return  # Login not required (i.e. user already logged in)? Debug with non-headless browser if errors propagate

    if len(sys.argv) < 2:
        print("ERROR: Improper CLI format")
        print("Please use: 'scraper.py <email@up.edu> [<password>]'")
        web_driver.quit()
        exit()

    email_value = sys.argv[1]
    if len(sys.argv) == 2:
        password_value = getpass()
    else:
        password_value = sys.argv[2]

    # Enter email/username
    email_input.send_keys(email_value)
    web_driver.find_element_by_id("idSIButton9").click()
    time.sleep(load_speed)

    # Enter password
    pass_input.send_keys(password_value)  # Hides password input to terminal
    web_driver.find_element_by_id("idSIButton9").click()
    time.sleep(load_speed)

    # Navigate off login page
    web_driver.find_element_by_id("idSIButton9").click()


# Returns a mapping of course names to course objects
def get_dict_entries_for_courses(courses: List[WebElement]) -> Dict[str, Course]:
    course_dict = {}

    for course in courses:
        if not course.text:
            continue

        course_name = format_course_name(course.text)
        course_dict[course_name] = Course(course_name, course.get_attribute("href"))

    return course_dict


# Generate a dictionary of all valid courses
def scrape_course_metadata(web_driver: WebDriver, load_speed: int) -> Dict[str, Course]:
    # Generate list of course metadata
    course_dict = {}
    try:
        # Set course overview to display all courses
        web_driver.find_element_by_id("groupingdropdown").click()
        course_overview = web_driver.find_element_by_id("inst279425")
        course_overview.find_element_by_xpath(".//a[@data-value='all']").click()

        # Scrape course metadata
        while True:
            course_overview = web_driver.find_element_by_id("inst279425")
            courses = course_overview.find_elements_by_class_name("coursename")
            course_dict.update(get_dict_entries_for_courses(courses))

            next_page = course_overview.find_element_by_xpath(".//li[@data-control='next']")
            if next_page.get_attribute("aria-disabled") == "true":
                break

            next_page.click()
            time.sleep(load_speed)

    except NoSuchElementException:
        print("ERROR: Unexpected course overview format")
        web_driver.quit()
        exit()

    return course_dict


# Retrieve assignment and resource files from each specified course
def download_course_data(web_driver: WebDriver, course_dict: Dict[str, Course]):
    # Traverse courses
    for course_name in course_dict:
        try:
            # Visit course page
            course = course_dict[course_name]
            visit_page(web_driver, course.url)
            course.html = web_driver.page_source

            # Traverse course file groups
            assignments = web_driver.find_elements_by_class_name("assign")
            resources = web_driver.find_elements_by_class_name("resource")

            assignment_files = scrape_assignments(assignments)
            resource_files = scrape_resources(resources)

            # Update course data
            course = download_assignments(web_driver, course, assignment_files)
            course_dict[course_name] = download_resources(course, resource_files)

        except NoSuchElementException:
            print("ERROR: Unexpected course assignment format")
            web_driver.quit()
            exit()

    return course_dict


# Extract assignment file urls and names from HTML elements
def scrape_assignments(files: List[WebElement]) -> Iterator[Tuple[str, str]]:
    file_names = [f.find_element_by_xpath(".//span[@class='instancename']").text for f in files]
    file_urls = [f.find_element_by_xpath(".//a").get_attribute("href") for f in files]
    return zip(file_names, file_urls)


# Download assignment files 
def download_assignments(web_driver: WebDriver, course: Course, assignments: Iterator[Tuple[str, str]]):
    for assign_name, assign_url in assignments:
        assign_name = format_default(assign_name)

        # Visit assignment page
        visit_page(web_driver, assign_url)

        # Download files
        display_hidden_files(web_driver)
        downloads = web_driver.find_elements_by_xpath("//div[@class='fileuploadsubmission']/a")

        download_names = [d.text for d in downloads]
        download_urls = [d.get_attribute("href") for d in downloads]

        if downloads:
            course.file_groups[assign_name] = []
            for download_name, url in zip(download_names, download_urls):
                name = download_url(url, format_default(download_name))
                course.file_groups[assign_name].append(name)

    return course


# Expand all hidden elements
def display_hidden_files(web_driver: WebDriver) -> None:
    # Show hidden files
    expand_icons = web_driver.find_elements_by_xpath("//a[@aria-expanded='false']")
    for icon in expand_icons:
        try:
            icon.click()
        except ElementNotVisibleException:
            continue  # Skip element


# Extract resource file urls and names from HTML elements
def scrape_resources(resources: List[WebElement]) -> Iterator[Tuple[str, str]]:
    file_names = [f.find_element_by_xpath(".//span[@class='instancename']").text for f in resources]
    file_urls = [f.find_element_by_xpath(".//a").get_attribute("href") for f in resources]
    return zip(file_names, file_urls)


# Download resource files
def download_resources(course: Course, resources: Iterator[Tuple[str, str]]) -> Course:
    for resource_name, resource_url in resources:
        resource_name = format_default(resource_name)

        name = download_url(resource_url, resource_name)
        course.file_groups[name] = name

    return course


# Retrieve a given file by url, return the file's name
def download_url(url: str, original_file_name: str, max_attempts: int = 64) -> str:
    all_downloads_finished()

    with urllib.request.urlopen(url) as response:
        file_name = original_file_name
        for i in range(1, max_attempts):
            try:
                with open("files/" + file_name, "wb") as files_directory:
                    shutil.copyfileobj(response, files_directory)
                return file_name
            except FileExistsError:  # Rename file to avoid conflicts
                file_name = f"{original_file_name} ({i})"

        return file_name


# Navigate to a specified url
def visit_page(web_driver: WebDriver, url: str) -> None:
    try:
        # Wait for all previous downloads to finish
        all_downloads_finished()
        web_driver.get(url)

    except InvalidArgumentException:
        print("ERROR: Malformed URL: ", url)
        web_driver.quit()
        exit()


# Determine whether all downloads have finished
def all_downloads_finished() -> None:
    while True:
        finished = True

        for file_name in os.listdir("files/"):
            if ".crdownload" in file_name:
                finished = False
                time.sleep(0.5)

        if finished:
            break


# Extract meaningful information from course name
def format_course_name(text: str) -> str:
    if "-" in text:
        text = text.rpartition("-")[-1].strip()
    if "\n" in text:
        text = text.rpartition("\n")[-1].strip()
    return format_default(text)


# Extract meaningful infromation from text
def format_default(text: str) -> str:
    text = remove_non_printable_chars(text)
    if "\n" in text:
        text = text.rpartition("\n")[0]
    return text.replace("/", " ").replace("?", " ").replace("*", " ").strip()


# Remove all non-printable characters
def remove_non_printable_chars(text: str) -> str:
    printable_set = set(string.printable)
    return ''.join(filter(lambda x: x in printable_set, text))


# Re-organize downloaded files to be grouped by course and assignments
def organize_files(course_dict: Dict[str, Course], root_directory_name: str) -> None:
    all_downloads_finished()
    for course_name in course_dict:
        course = course_dict[course_name]

        # Create sub-folder for course
        if course.file_groups:
            course_path = root_directory_name + course_name + "/"
            if not os.path.isdir(course_path):
                os.mkdir(course_path)

                if course.html:
                    with open(course_path + course_name + ".html", "w") as course_html_file:
                        course_html_file.write(course.html)

            for group_name in course.file_groups:
                file_group = course.file_groups[group_name]

                if not isinstance(file_group, list):
                    move_file(file_group, root_directory_name, course_path)

                elif file_group:
                    group_path = course_path + group_name + "/"
                    if not os.path.isdir(group_path):
                        os.mkdir(group_path)

                    for file_name in file_group:
                        move_file(file_name, root_directory_name, group_path)


# Move a file to the proper sub-directory
def move_file(file_name: str, root_directory_name: str, group_path: str) -> None:
    try:
        os.rename(root_directory_name + file_name, group_path + file_name)
    except FileNotFoundError:
        # TODO: should this be a raw string instead?
        file_name_regex = file_name + "( \([0-9]+\))?"
        for name in os.listdir(root_directory_name):
            if re.match(file_name_regex, name):
                os.rename(root_directory_name + name, group_path + name)


# endregion Helper Methods

# region Main

# Create driver and access Moodle
def main_function() -> None:
    chrome_web_driver = setup_chrome_web_driver(5)
    query_moodle(chrome_web_driver)
    login_to_moodle(chrome_web_driver, 1)

    # Visit each course and download all relevant files
    courses = scrape_course_metadata(chrome_web_driver, 1)
    courses = download_course_data(chrome_web_driver, courses)

    # Re-organize files
    organize_files(courses, "files/")


main_function()

# endregion Main
