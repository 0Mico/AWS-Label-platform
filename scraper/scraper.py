import os
import json
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
import dotenv

import awsutils as aws_ut

# Make an http get request to the url. Returns the response content
def _makeHTTPRequest(url: str):
    response = requests.get(url)
    return response.text

# Elaborate the response using BeautifulSoup's html parser
def _organizeResponse(response: str):
    soup = BeautifulSoup(response, "html.parser")
    return soup

# Extract the list of job cards in the given web page    
def _extractJobCardsFromHTML(web_page: BeautifulSoup):
    job_cards = web_page.select("li div.base-card")
    return job_cards

# Extract the job_id from the card received
def _extactJobIDFromHTML(job_card: Tag):
    job_id = job_card.get("data-entity-urn").split(":")[3]
    if job_id: return job_id
    else: return ''

# Use css selectors to extract the job title from the card received
def _extractTitleFromHTML(job_card: Tag):
    tag = job_card.select_one("a span")
    if tag:
        title = tag.get_text().strip()
        if title: return title
    else: return ''

# Extract the company name from the card received
def _extractCompanyNameFromHTML(job_card: Tag):
    tag = job_card.select_one("h4 a")
    if tag:
        company_name = tag.get_text().strip()
        if company_name: return company_name
    else: return ''

# Extract the location of the job from the card received
def _extractJobLocationFromHTML(job_card: Tag):
    tag = job_card.select_one("span.job-search-card__location")
    if tag:
        location = tag.get_text().strip()
        if location: return location
    else: return ''

# Extract the pubblication date of the job post
def _extractPubblicationDateFromHTML(job_card: Tag):
    tag = job_card.select_one("time")
    if tag:
        date = tag.get('datetime')
        if date: return date
    else: return ''

# Extract the link to go to the job page
def _goToJobPage(base_url: str, job_id: str):
    url = base_url + job_id
    response = _makeHTTPRequest(url)
    return response

# Extract the job description to retrieve then skills required
# Extract text recursively from the "container tag" that contains the entire description
def _extractJobDescriptionFronHTML(web_page: BeautifulSoup):
    tag = web_page.select_one("div.show-more-less-html__markup")
    if tag:
        description = tag.get_text().strip()
        if description == "":
            print("searching in child tags")
            for child in tag.descendants:
                description = description.join(child.get_text().strip())
        return description
    else: return ''

# Update the url with the number of job_posting already scraped
def _modifyUrl(url: str, new_start: int):
    parsed_url = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    query_params['start'] = [str(new_start)]
    new_query_string = urllib.parse.urlencode(query_params, doseq=True)
    new_url = parsed_url._replace(query=new_query_string).geturl()
    return new_url

# Create a JSON object for each job_card received
def _createJobObject(job_card: Tag):
    job = {}
    job['Job_ID'] = _extactJobIDFromHTML(job_card)
    job['Title'] = _extractTitleFromHTML(job_card)
    job['Company_name'] = _extractCompanyNameFromHTML(job_card)
    job['Location'] = _extractJobLocationFromHTML(job_card)
    job['Pubblication_date'] = _extractPubblicationDateFromHTML(job_card)

    response = _goToJobPage(os.getenv("SINGLE_JOB_BASE_LINK"), job['Job_ID'])
    soup = _organizeResponse(response)
 
    job['Description'] = _extractJobDescriptionFronHTML(soup)
    job['Sent_to_queue'] = False

    return job

# Make a json object for each job scraped and write it into a json file   
def scrapeJobs(url: str, post_scraped: int, db_table, sqs_queue_url):
    print(url) 
    response = _makeHTTPRequest(url)
    soup = _organizeResponse(response)
    job_cards = _extractJobCardsFromHTML(soup)
    jobs_retrieved = len(job_cards)
    
    for card in job_cards:
        job = _createJobObject(card)

        result_job = aws_ut._checkIfJobExists(db_table, job['Job_ID']) # The response is a dict of jobs

        if result_job is None:
            aws_ut._saveJobToDynamoDB(db_table, job)
            if job['Description'] != '':
                aws_ut._writeJobToSQSQueue(sqs_queue_url, job)

        else:
            if result_job['Sent_to_queue']:
                continue
            else:
                if job['Description'] != '':
                    aws_ut._writeJobToSQSQueue(sqs_queue_url, job)

        with open("LinkedinJobPosts.json", "a") as file:
            json.dump(job, file, indent=4)
            file.write('\n')

    if jobs_retrieved > 0:
        post_scraped += jobs_retrieved
        new_url = _modifyUrl(url, post_scraped)
        
        #To not make the server reset the connection due to too much requests in the unit of time
        time.sleep(1)

        scrapeJobs(new_url, post_scraped, db_table, sqs_queue_url)


def main():
    dotenv.load_dotenv()

    aws_ut._setupAWSSession()
    db_table = aws_ut._retrieveDynamoDBTable(os.getenv("DYNAMODB_TABLE_NAME"))    
    sqs_queue_url = aws_ut._retrieveSQSQueueUrl(os.getenv("DEDUPLICATED_JOBS_QUEUE_NAME"))

    keywords = ['Data+Analyst', 'Data+Scientist', 'Cloud+Engineer', 'Devops', 'Frontend+Developer', 'Backend+Developer', 
                'Software+Engineer', 'Fullstack+Developer', 'Mobile+Developer', 'Game+Developer', 'Artificial+Intelligence',
                'Python+Developer']

    for k in keywords:
        start_url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={k}&geoId=103350119&start=0"
        post_scraped = 0
        scrapeJobs(start_url, post_scraped, db_table, sqs_queue_url)


if __name__ == "__main__":
    main()