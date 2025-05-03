from flask import jsonify
from flask import Flask,render_template, request, session  # https://www.geeksforgeeks.org/pass-javascript-variables-to-python-in-flask/
import redis  # NEW
from uuid import uuid4  # NEW

app = Flask(__name__,template_folder="templates")
app.secret_key = 'supersecretkey'

# Connect to Redis
r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

MAX_USERS = 10

# Utility function to limit users
@app.before_request
def limit_users():
    user_id = session.get('user_id')

    # If user is not logged in
    if not user_id:
        if r.scard("active_users") >= MAX_USERS:
            return "User limit reached. Try again later.", 503
        # Assign a new unique user ID and track
        user_id = str(uuid4())
        session['user_id'] = user_id
        r.sadd("active_users", user_id)  # Add user to Redis set

@app.teardown_request
def remove_user(exception=None):
    # Cleanup user on session end (when the user logs out or session expires)
    user_id = session.pop('user_id', None)
    if user_id:
        r.srem("active_users", user_id)  # Remove user from Redis set


@app.route("/")
def hello():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    data = request.form.get('data')
    import requests

    # Create a request header or else we will get the 403 error
    headers = {'User-Agent': "fin22144@uom.edu.gr"}

    base_url_1 = 'https://data.sec.gov/api/xbrl/companyfacts/CIK' 
    base_url = 'https://data.sec.gov/api/xbrl/companyconcept/CIK'

    companies_tickers = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
    tickers_data = companies_tickers.json()
    
    def getCikCode(ticker):
        ticker = ticker.upper() 
        for company_id in tickers_data:
            company = tickers_data[company_id]
            if company['ticker'] == ticker:
                cik_str = str(company['cik_str']).zfill(10) 
                return cik_str 
        return "Doesn't have a CIK code"

    cik_code = getCikCode(data)
    
    def DetectCompanyTaxonomy(CIK):
        url= f"{base_url_1}{CIK}.json"
        print(url)
        response = requests.get(url,headers=headers)
        stock_data = response.json()
        list_with_taxonomies = list(stock_data.get('facts').keys())
        if 'us-gaap' in list_with_taxonomies:
            return 'us-gaap'
        elif 'ifrs-full' in list_with_taxonomies:
            return 'ifrs-full'
        else:
            #print('Company doesn't have IFRS or US-GAAP')
            return "Company doesn't have IFRS or US-GAAP"
        
    def GetStockData(CIK):
        # Check for the facts key
        if taxonomy == 'us-gaap':
            field = "NetIncomeLoss" 
        elif taxonomy == 'ifrs-full':
            field = "ProfitLoss"
        
        url = f"{base_url}{CIK}/{taxonomy}/{field}.json"
        print(url)
        response = requests.get(url,headers=headers)
        stock_data = response.json() 

        currency = list(stock_data['units'].keys())[0]
        print(f"Currency detected: {currency}")
        
        records = stock_data['units'][currency]

        def myFunc(e): 
            return e['end']

        records.sort(reverse=True, key=myFunc) 

        recent_records = records[:120] # Take the most recent records sorted from new to old 

        #print(type(recent_records[0]['end'])) = <class 'str'>

        simplified_records_1 = []
        simplified_records_2 = []

        for record in recent_records:
            fp = record.get('fp')
            fy = record.get('fy')  
            val = record.get('val')
            start = record.get('start')
            end = record.get('end')
            filed = record.get('filed')

            if fp == 'FY':
                simplified_records_1.append({'fp': fp, 'fy': fy, 'val': val, 'start':start, 'end': end, 'filed': filed})

            if fp and fp.startswith("Q"):
                simplified_records_2.append({'fp': fp, 'fy' : fy, "val": val, 'start': start, 'end':end , 'filed': filed})

        from datetime import datetime 

        latest_by_fy = {}

        for entry in simplified_records_1:
            fy = entry['fy']
            end_date = datetime.strptime(entry['end'], "%Y-%m-%d") 
           
            if fy not in latest_by_fy or end_date > datetime.strptime(latest_by_fy[fy]['end'], "%Y-%m-%d"):
                latest_by_fy[fy] = entry

        
        result_1 = list(latest_by_fy.values())

        result_2 = []
        for entry in simplified_records_2:
            start_date = datetime.strptime(entry['start'], "%Y-%m-%d")
            end_date = datetime.strptime(entry['end'], "%Y-%m-%d") 
            difference = end_date - start_date

            #print(type(difference.days))  = <class 'int'>

            if difference.days > 70 and difference.days < 100: 
                if entry not in result_2:
                    result_2.append(entry)
                 
        result = result_1 + result_2

        final_result = sorted(result, key=lambda x: datetime.strptime(x['end'], "%Y-%m-%d"), reverse=True) # Sort thr list based on the end date https://stackoverflow.com/questions/16310015/what-does-this-mean-key-lambda-x-x1
   
        latest_entries = {} # Dictionary to hold the latest 'filed' version for each (start, end) period

        for item in final_result:
            key = (item['start'], item['end'])
            current_filed = datetime.strptime(item['filed'], "%Y-%m-%d")
            if key not in latest_entries or datetime.strptime(latest_entries[key]['filed'], "%Y-%m-%d") < current_filed:
                latest_entries[key] = item
            
        final_clean_result = list(latest_entries.values())
        return final_clean_result

    def CleanOutput(output):
        for r in output:
            if r['fp'].startswith('Q'):
                r['fp'] = 'Quarter'
            elif r['fp'].startswith('FY'):
                r['fp'] = 'Full Year'
        return output

    if cik_code == "Doesn't have a CIK code":
        return cik_code
    else:
        print(cik_code)
        taxonomy = DetectCompanyTaxonomy(cik_code)

        if taxonomy == "Company doesn't has IFRS or US-GAAP":
            return taxonomy
        else:
            output = GetStockData(cik_code)
            clean_output = CleanOutput(output)
            return  jsonify({'result': clean_output[:30]})
        
if __name__ == '__main__':
    app.run()


