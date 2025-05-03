#Retrieve the TTM Net income for the last 5 Years.
#5 Years are usually 20 Quarters, (1 Year = 4 Quarters)
#Each Quarter must have its own TMM

#So at the end, I need 20TTMs
#I also need to retrieve the shares outstanding for those 5 years
from flask import jsonify
from flask import Flask,render_template, request # https://www.geeksforgeeks.org/pass-javascript-variables-to-python-in-flask/

app = Flask(__name__,template_folder="templates")

@app.route("/")
def hello():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    data = request.form.get('data')
    
    # process the data using Python code
    # We are gonna need to install this library first
    import requests

    # Create a request header or else we will get the 403 error
    headers = {'User-Agent': "jordansapanidis01@gmail.com"}

    base_url_1 = 'https://data.sec.gov/api/xbrl/companyfacts/CIK' # We use this Api to find the company taxonomy
    base_url = 'https://data.sec.gov/api/xbrl/companyconcept/CIK'

    #Get all the tickers and cik data so that we will be able to find a cik code based on the ticker of a company
    companies_tickers = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
    tickers_data = companies_tickers.json()
    
    #function that find the cik_str based on the ticker
    def getCikCode(ticker):
        ticker = ticker.upper() # Convert the ticker in uppercase
        for company_id in tickers_data:
            company = tickers_data[company_id] # Access each company dictionary
            if company['ticker'] == ticker:
                cik_str = str(company['cik_str']).zfill(10) # zfill(x) string Fills the string with a specified number of 0 values at the beginning until x
                return cik_str
        # If the ticker is not found 
        #print("Doesn't have a CIK code")
        return "Doesn't have a CIK code"

    cik_code = getCikCode(data)
    
        #function that detect the taxonomy
    def DetectCompanyTaxonomy(CIK):
        url= f"{base_url_1}{CIK}.json"
        print(url)
        response = requests.get(url,headers=headers)
        stock_data = response.json()
        #print(stock_data['facts'].keys())
        list_with_taxonomies = list(stock_data.get('facts').keys())
        #print(f"Taxonomies found: {list_with_taxonomies}")
        if 'us-gaap' in list_with_taxonomies:
            #print('Company uses US-GAAP taxonomy')
            return 'us-gaap'
        elif 'ifrs-full' in list_with_taxonomies:
            #print('Company uses IFRS  taxonomy')
            return 'ifrs-full'
        else:
            #print('Company doesn't has IFRS or US-GAAP')
            return "Company doesn't has IFRS or US-GAAP"
        
    # Take the Net Income for the last Quarters
    def GetStockData(CIK):
        # Check for the facts key
        if taxonomy == 'us-gaap':
            field = "NetIncomeLoss" # https://xbrl.us/wp-content/uploads/2015/03/PreparersGuide.pdf 
        elif taxonomy == 'ifrs-full':
            field = "ProfitLoss"
        
        url = f"{base_url}{CIK}/{taxonomy}/{field}.json"
        print(url)
        response = requests.get(url,headers=headers)
        stock_data = response.json() 

        # Detect the currency key dynamically (e.g., 'USD', 'EUR', etc.)
        currency = list(stock_data['units'].keys())[0]
        print(f"Currency detected: {currency}")

        #print(stock_data['units'])
        #print(stock_data.keys())

        records = stock_data['units'][currency]

        def myFunc(e): 
            return e['end']

        records.sort(reverse=True, key=myFunc) # Sort the quarters list based on the end date 

        #print(type(records)) 
        #print(dir(records))
        #print(records[len(records)-1])
        #print(records)

        recent_records = records[:120] # Take the most recent records sorted from new to old 

        #print(recent_records)
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
                # Keep full-year records
                simplified_records_1.append({'fp': fp, 'fy': fy, 'val': val, 'start':start, 'end': end, 'filed': filed})

            if fp and fp.startswith("Q"):
                simplified_records_2.append({'fp': fp, 'fy' : fy, "val": val, 'start': start, 'end':end , 'filed': filed})

        #print(simplified_records_2)

        from datetime import datetime # https://www.w3schools.com/python/python_datetime.asp

        # create a dict to keep only latest per 'fy'
        latest_by_fy = {}

        for entry in simplified_records_1:
            fy = entry['fy']
            end_date = datetime.strptime(entry['end'], "%Y-%m-%d") # strptime method https://www.geeksforgeeks.org/python-datetime-strptime-function/
            # If this fy is not stored yet, or if this date is newer, replace it
            if fy not in latest_by_fy or end_date > datetime.strptime(latest_by_fy[fy]['end'], "%Y-%m-%d"):
                latest_by_fy[fy] = entry

        # final result: only latest per fy
        result_1 = list(latest_by_fy.values())

        # print nicely
        #for item in result:
            #print(item)
        #print(simplified_records_1)

        #Remove duplicates in Q's
        result_2 = []
        for entry in simplified_records_2:
            start_date = datetime.strptime(entry['start'], "%Y-%m-%d")
            end_date = datetime.strptime(entry['end'], "%Y-%m-%d") 
            difference = end_date - start_date
            
            #print(difference.days)
            #print(type(difference.days))  = <class 'int'>

            if difference.days > 70 and difference.days < 100: #check for 3 month quarters 
                if entry not in result_2:
                    result_2.append(entry)
            
        #print(result_1)  
        #print(result_2)
        
        # Combine those to result lists to one final
        result = result_1 + result_2
        #print(result)

        final_result = sorted(result, key=lambda x: datetime.strptime(x['end'], "%Y-%m-%d"), reverse=True) # Sort thr list based on the end date https://stackoverflow.com/questions/16310015/what-does-this-mean-key-lambda-x-x1
        
        #print(final_result) = a list of dictionaries
        #for item in final_result:
            #print(item)

        latest_entries = {} # Dictionary to hold the latest 'filed' version for each (start, end) period

        for item in final_result:
            key = (item['start'], item['end'])
            current_filed = datetime.strptime(item['filed'], "%Y-%m-%d")
            if key not in latest_entries or datetime.strptime(latest_entries[key]['filed'], "%Y-%m-%d") < current_filed:
                latest_entries[key] = item
            
        #print(latest_entries)

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
        #print(type(cik_code))
        #print(dir(cik_code))
        print(cik_code)
        taxonomy = DetectCompanyTaxonomy(cik_code)

        if taxonomy == "Company doesn't has IFRS or US-GAAP":
            return taxonomy
        else:
            output = GetStockData(cik_code)
            #print(output)
            #for item in output:
                #print(item)
            clean_output = CleanOutput(output)
            return  jsonify({'result': clean_output[:30]})
        



if __name__ == '__main__':
    app.run()


'''

    #url= f"{base_url}{CIK}.json"
    #print(url)
    #response = requests.get(url,headers=headers)
    #stock_data = response.json()

    #print(stock_data.keys())
    #print(stock_data['filings'].keys())
    ##############################################
    
'''
