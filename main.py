import streamlit as st
import requests
import re
import openai
import pandas as pd
import os

openai.api_key = st.secrets['OPENAI_API_KEY']

def get_profile_id(url):
    # Updated regex to account for optional country code, optional 'www.', and optional trailing slash
    match = re.search(r'https:\/\/(?:[a-z]{2}\.|www\.)?linkedin\.com\/in\/([^\/]+)\/?', url)
    if match:
        return match.group(1)
    else:
        return None

# Streamlit app
def app():
    st.title("LinkedIn Headline Generator")

    # Input for LinkedIn profile url with tooltip
    url = st.text_input("Enter your LinkedIn profile url", help="Paste in your LinkedIn url and hit enter (eg. 'https://www.linkedin.com/in/brianchesky')")

    if url:
        profile_id = get_profile_id(url)

        if profile_id:
            # Make POST request to get profile details
            url = "https://linkedin-profiles-and-company-data.p.rapidapi.com/profile-details"
            headers = {
                "content-type": "application/json",
                "X-RapidAPI-Key": "9c1847dc95msh72942d9ba1779e6p14cfc2jsn060cb7a3a6b0",
                "X-RapidAPI-Host": "linkedin-profiles-and-company-data.p.rapidapi.com"
            }
            data = {
                "profile_id": profile_id,
                "profile_type": "personal",
                "contact_info": True,
                "recommendations": False,
                "related_profiles": False
            }
            try:
                response = requests.post(url, json=data, headers=headers)
                response.raise_for_status()
                profile_info = response.json()
            except requests.exceptions.RequestException as e:
                st.error(f"Error: {e}")
                return

            try:
                name = f"{profile_info['first_name']} {profile_info['last_name']}"
            except KeyError:
                st.error("Error: Unable to retrieve profile information.")
                return

            with st.expander(name, expanded=True):
                col1, col2 = st.columns([1,7])
            
                with col1:
                    # Display profile picture as a circle
                    if 'profile_picture' in profile_info and profile_info['profile_picture'] is not None:
                        st.image(profile_info['profile_picture'], width=125, use_column_width=True, clamp=True)
                        st.markdown("<style>.image-container img { border-radius: 50%; overflow: hidden; }</style>", unsafe_allow_html=True)
                with col2:
                    data = {
                        "Name": name if 'first_name' in profile_info and 'last_name' in profile_info else '',
                        "Headline": profile_info['sub_title'] if 'sub_title' in profile_info else '',
                        "Location": profile_info['location']['short'] if 'location' in profile_info and 'short' in profile_info['location'] else '',
                        "Title": profile_info['position_groups'][0]['profile_positions'][0]['title'] if 'position_groups' in profile_info and profile_info['position_groups'] and 'profile_positions' in profile_info['position_groups'][0] and profile_info['position_groups'][0]['profile_positions'] and 'title' in profile_info['position_groups'][0]['profile_positions'][0] else '',
                        "Company": profile_info['position_groups'][0]['profile_positions'][0]['company'] if 'position_groups' in profile_info and profile_info['position_groups'] and 'profile_positions' in profile_info['position_groups'][0] and profile_info['position_groups'][0]['profile_positions'] and 'company' in profile_info['position_groups'][0]['profile_positions'][0] else '',
                        "Website": profile_info['contact_info']['websites'][0]['url'] if 'contact_info' in profile_info and 'websites' in profile_info['contact_info'] and profile_info['contact_info']['websites'] and 'url' in profile_info['contact_info']['websites'][0] else '',
                    }
                    # Convert dictionary to DataFrame
                    df = pd.DataFrame(data, index=[0])
                    # Use Streamlit's data grid for displaying the DataFrame
                    st.table(df.set_index('Name').T)

            # Automatically fetch company info if available
            if 'url' in profile_info['position_groups'][0]['company']:
                url = "https://linkedin-company-data.p.rapidapi.com/linkedInCompanyDataJson"
                payload = { "liUrls": [profile_info['position_groups'][0]['company']['url']] }
                headers = {
                    "content-type": "application/json",
                    "X-RapidAPI-Key": "9c1847dc95msh72942d9ba1779e6p14cfc2jsn060cb7a3a6b0",
                    "X-RapidAPI-Host": "linkedin-company-data.p.rapidapi.com"
                }
                try:
                    response = requests.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    company_info = response.json()
                except requests.exceptions.RequestException as e:
                    st.error(f"Error: {e}")
                    return

                with st.expander(company_info['results'][0]['company_name'] if 'company_name' in company_info['results'][0] else 'Company Info', expanded=False):
                    col1, col2 = st.columns([1,7])
                    with col1:
                        if 'logo' in company_info['results'][0]:
                            st.image(company_info['results'][0]['logo'], width=125, use_column_width=True, clamp=True)
                    with col2:
                        company_data = {
                            "Company Name": company_info['results'][0]['company_name'] if 'company_name' in company_info['results'][0] else '',
                            "Company Size": company_info['results'][0]['company_size'] if 'company_size' in company_info['results'][0] else '',
                            "Slogan": company_info['results'][0]['slogan'] if 'slogan' in company_info['results'][0] else '',
                            "Description": company_info['results'][0]['description'] if 'description' in company_info['results'][0] else '',
                            "Specialties": ', '.join(company_info['results'][0]['specialties']) if 'specialties' in company_info['results'][0] else ''
                        }
                        # Convert dictionary to DataFrame
                        df = pd.DataFrame(company_data, index=[0])
                        # Use Streamlit's table for displaying the DataFrame
                        st.table(df.set_index('Company Name').T)

                # Add the expander
                with st.expander("Headline Generator Context", expanded=False):
                    # Title and Company
                    title_and_company = f"{profile_info['position_groups'][0]['profile_positions'][0]['title']} at {profile_info['position_groups'][0]['profile_positions'][0]['company']}"

                    # Who do you help?
                    prompt = f"Your job is to identify who this company helps, who are they serving, return only the name for that group in 10 words or less. Context: {company_info['results'][0]['description']}"
                    try:
                        response = openai.ChatCompletion.create(
                            model="gpt-4",
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant."},
                                {"role": "user", "content": prompt}
                            ]
                        )
                        who_help = response.choices[0].message['content'].strip()
                    except Exception as e:
                        st.error(f"Error: {e}")
                        return

                    # What do you help them with?
                    prompt = f"Your job is to identify what this company does for their clients, summarize their solution in 10 words or less. Context: {company_info['results'][0]['description']}"
                    try:
                        response = openai.ChatCompletion.create(
                            model="gpt-4",
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant."},
                                {"role": "user", "content": prompt}
                            ]
                        )
                        what_help = response.choices[0].message['content'].strip()
                    except Exception as e:
                        st.error(f"Error: {e}")
                        return

                    # Related keywords
                    if 'specialties' in company_info['results'][0]:
                        prompt = f"Identify 3 of the top keywords that would be an accurate descriptor of what the company does and are terms most likely to be searched for by something looking for those services. Return only those keywords no explanation. Context: {company_info['results'][0]['description']} {', '.join(company_info['results'][0]['specialties'])}"
                        try:
                            response = openai.ChatCompletion.create(
                                model="gpt-4",
                                messages=[
                                    {"role": "system", "content": "You are a helpful assistant."},
                                    {"role": "user", "content": prompt}
                                ]
                            )
                            related_keywords = response.choices[0].message['content'].strip()
                        except Exception as e:
                            st.error(f"Error: {e}")
                            return
                    else:
                        related_keywords = ""

                    # Create a DataFrame to display the information
                    data = {
                        "Title and Company": title_and_company,
                        "Who do you help?": who_help,
                        "What do you help them with?": what_help,
                        "Related keywords": related_keywords
                    }
                    df = pd.DataFrame(data, index=[0])
                    st.data_editor(df.T)
            # Generate new LinkedIn headline            
            if st.button('Generate Headlines', key=None, help=None):
                prompt = f"Generate exactly 9 distinct headlines for a LinkedIn profile based on the provided format and criteria. There should be no additional labels, groupings, or options. Just a numbered list from 1 to 9. Format: Title at Company | Benefit-oriented statement | Big accomplishment (if available) | Top Keyword #1 | Top Keyword #2.  Context: - Title at Company: {title_and_company} - Who is helped: {who_help} - What they help accomplish: {what_help} - Relevant keywords: {related_keywords}. For headline results 1-3, use a Professional tone. For headline results 4-6, use a Casual tone and for headlines 7-9 use a Fun tone with emojis. Each headline must be under 220 characters. Your output should be a numbered list of headlines 9 in total. "
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=1000,
                    )
                except Exception as e:
                    st.error(f"Error: {e}")
                    return

                # Display the generated headlines as text output
                st.write("Suggested Headlines:")
                headlines = [f"{choice.message['content'].strip()}" for i, choice in enumerate(response.choices)]
                for headline in headlines:
                    st.markdown(headline)

if __name__ == "__main__":
    app()
