# Author: Bishal Sarang
import json
import pickle
import time

import colorama
import requests
from colorama import Back, Fore
from ebooklib import epub
from utils import *
import epub_writer
import markdown
import re
from bs4 import BeautifulSoup

# Initialize Colorama
colorama.init(autoreset=True)

# Get upto which problem it is already scraped from track.conf file
completed_upto = read_tracker("track.conf")

# Load chapters list that stores chapter info
# Store chapter info
with open('chapters.pickle', 'rb') as f:
    chapters = pickle.load(f)

def download(problem_num, url, title, title_slug):  
    print(Fore.BLACK + Back.CYAN + f"Fetching problem num " + Back.YELLOW + f" {problem_num} " + Back.CYAN + " with url " + Back.YELLOW + f" {url} ")
    n = len(title)

    try:
        graphql_url = "https://leetcode.com/graphql"
        payload = {
            "operationName": "questionData",
            "variables": {"titleSlug": title_slug},
            "query": "query questionData($titleSlug: String!) {\n  question(titleSlug: $titleSlug) {\n    content\n  }\n}\n"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }
        
        response = requests.post(graphql_url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        question_content = data.get("data", {}).get("question", {}).get("content", "")
        if not question_content:
            raise ValueError("No content found for problem")

        # Fetch the solutions list
        query_list = """
        query communitySolutions($questionSlug: String!, $skip: Int!, $first: Int!, $query: String, $orderBy: TopicSortingOption, $languageTags: [String!], $topicTags: [String!]) {
          questionSolutions(
            filters: {questionSlug: $questionSlug, skip: $skip, first: $first, query: $query, orderBy: $orderBy, languageTags: $languageTags, topicTags: $topicTags}
          ) {
            solutions {
              id
              title
            }
          }
        }
        """
        payload_list = {
            "query": query_list,
            "variables": {
                "query": "",
                "languageTags": [],
                "topicTags": [],
                "questionSlug": title_slug,
                "skip": 0,
                "first": 5,
                "orderBy": "most_votes"
            },
            "operationName": "communitySolutions"
        }
        resp_list = requests.post(graphql_url, json=payload_list, headers=headers)
        resp_list.raise_for_status()
        list_data = resp_list.json()
        
        solution_content_html = ""
        solutions = list_data.get("data", {}).get("questionSolutions", {}).get("solutions", [])
        if len(solutions) >= 2:
            second_sol = solutions[1]
            topic_id = second_sol["id"]
            sol_title = second_sol.get("title", "Community Solution")
            
            # Fetch the actual solution content
            query_detail = """
            query communitySolution($topicId: Int!) {
              topic(id: $topicId) {
                id
                title
                post {
                  content
                }
              }
            }
            """
            payload_detail = {
                "query": query_detail,
                "variables": {"topicId": topic_id},
                "operationName": "communitySolution"
            }
            resp_detail = requests.post(graphql_url, json=payload_detail, headers=headers)
            resp_detail.raise_for_status()
            detail_data = resp_detail.json()
            post_content = detail_data.get("data", {}).get("topic", {}).get("post", {}).get("content", "")
            
            if post_content:
                post_content = post_content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                post_content = re.sub(r'```([a-zA-Z\+\#]*)(?:\s*\[\])?', r'```\1', post_content)
                
                html = markdown.markdown(post_content, extensions=['fenced_code'])
                soup = BeautifulSoup(html, 'html.parser')
                
                html_post_content = ""
                for pre in soup.find_all('pre'):
                    code_tag = pre.find('code')
                    actual_code = code_tag.get_text() if code_tag else pre.get_text()
                    actual_code = actual_code.strip()
                    
                    if len(actual_code) > 20 and ("class " in actual_code or "def " in actual_code or "{" in actual_code or "return " in actual_code):
                        escaped_code = actual_code.replace('<', '&lt;').replace('>', '&gt;')
                        html_post_content += f"<div style='background-color: #282c34; color: #abb2bf; padding: 15px; border-radius: 5px; margin-bottom: 15px; font-family: monospace; overflow-x: auto; white-space: pre;'><pre style='margin: 0;'><code>{escaped_code}</code></pre></div>\n"
                
                if html_post_content:
                    solution_content_html = f"<hr><br><h2>Solution Code: {sol_title}</h2><br><div class='solution-content'>" + html_post_content + "</div>"

        # Construct HTML
        title_decorator = '*' * n
        problem_title_html = title_decorator + f'<div id="title">{title}</div>' + '\n' + title_decorator
        problem_html = problem_title_html + question_content + '<br><br>' + solution_content_html + '<br><br><hr><br>'

        # Append Contents to a HTML file
        with open("out.html", "ab") as f:
            f.write(problem_html.encode(encoding="utf-8"))
        
        # create and append chapters to construct an epub
        c = epub.EpubHtml(title=title, file_name=f'chap_{problem_num}.xhtml', lang='hr')
        c.content = problem_html
        chapters.append(c)

        # Write List of chapters to pickle file
        dump_chapters_to_file(chapters)
        # Update upto which the problem is downloaded
        update_tracker('track.conf', problem_num)
        print(Fore.BLACK + Back.GREEN + f"Writing problem num " + Back.YELLOW + f" {problem_num} " + Back.GREEN + " with url " + Back.YELLOW + f" {url} " )
        print(Fore.BLACK + Back.GREEN + " successfull ")

    except Exception as e:
        print(Back.RED + f" Failed Writing!!  {e} ")

def main():

    # Leetcode API URL to get json of problems on algorithms categories
    ALGORITHMS_ENDPOINT_URL = "https://leetcode.com/api/problems/algorithms/"

    # Problem URL is of format ALGORITHMS_BASE_URL + question__title_slug
    # If question__title_slug = "two-sum" then URL is https://leetcode.com/problems/two-sum
    ALGORITHMS_BASE_URL = "https://leetcode.com/problems/"

    # Load JSON from API
    algorithms_problems_json = requests.get(ALGORITHMS_ENDPOINT_URL).content
    algorithms_problems_json = json.loads(algorithms_problems_json)

    styles_str = "<style>pre{white-space:pre-wrap;background:#f7f9fa;padding:10px 15px;color:#263238;line-height:1.6;font-size:13px;border-radius:3px margin-top: 0;margin-bottom:1em;overflow:auto}b,strong{font-weight:bolder}#title{font-size:16px;color:#212121;font-weight:600;margin-bottom:10px}hr{height:10px;border:0;box-shadow:0 10px 10px -10px #8c8b8b inset}</style>"
    with open("out.html", "ab") as f:
            f.write(styles_str.encode(encoding="utf-8"))

    # List to store question_title_slug
    links = []
    for child in algorithms_problems_json["stat_status_pairs"]:
            # Only process free problems
            if not child["paid_only"]:
                question__title_slug = child["stat"]["question__title_slug"]
                question__article__slug = child["stat"]["question__article__slug"]
                question__title = child["stat"]["question__title"]
                frontend_question_id = child["stat"]["frontend_question_id"]
                difficulty = child["difficulty"]["level"]
                links.append((question__title_slug, difficulty, frontend_question_id, question__title, question__article__slug))

    # Sort by difficulty follwed by problem id in ascending order
    links = sorted(links, key=lambda x: (x[1], x[2]))

    try: 
        for i in range(completed_upto + 1, len(links)):
             question__title_slug, _ , frontend_question_id, question__title, question__article__slug = links[i]
             url = ALGORITHMS_BASE_URL + question__title_slug
             title = f"{frontend_question_id}. {question__title}"

             # Download each file as html and write chapter to chapters.pickle
             download(i, url , title, question__title_slug)

             # Sleep for 2 secs for each problem and 2 mins after every 30 problems
             if i > 0 and i % 30 == 0:
                 print(f"Sleeping 120 secs\n")
                 time.sleep(120)
             else:
                 print(f"Sleeping 2 secs\n")
                 time.sleep(2)

    finally:
        pass
    
    try:
        epub_writer.write("Leetcode Questions.epub", "Leetcode Questions", "Anonymous", chapters)
        print(Back.GREEN + "All operations successful")
    except Exception as e:
        print(Back.RED + f"Error making epub {e}")
    


if __name__ == "__main__":
    main()
