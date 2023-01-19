from flask import Flask, request, jsonify, make_response
from flask_restful import Api
from flask_httpauth import HTTPBasicAuth
from datetime import datetime
import pytz
from pytz import timezone
import numpy as np
import pandas as pd
import pandas as pd
import psycopg2
from sklearn import mixture

def gauss_m_m(data_set):
    # reshape data for gmm
    x = data_set.iloc[:,0].values
    f = x.reshape(-1,1)

    # finding the min BIC for select the number of components
    bics = []
    min_bic = 0
    counter = 1
    for i in range (10): 
        gmm = mixture.GaussianMixture(n_components = counter, max_iter=1000, random_state=0, covariance_type = 'full')
        gmm.fit(f)
        bic = gmm.bic(f)
        bics.append(bic)
        if bic < min_bic or min_bic == 0:
            min_bic = bic
            opt_bic = counter
        counter = counter + 1
    optimal_comp = opt_bic  # type: ignore // optimum component number
    
    # Gaussian mixture model
    g = mixture.GaussianMixture(n_components = optimal_comp, covariance_type="full")
    g.fit(f)
    weights = g.weights_
    means = g.means_
    covars = g.covariances_
    threshold = np.mean(means)
    return threshold, optimal_comp, weights, means, covars

# connection with PostgreSQL 
connection = psycopg2.connect(database = "your_database_name", user = "your_posgre_username", password = "your_postgre_password", host = "IP", port = "port")

# creating table if its not already exist
CREATE_VAL_TABLE = """CREATE TABLE IF NOT EXISTS val (id SERIAL PRIMARY KEY, gaussian_cnumber DOUBLE PRECISION, threshold DOUBLE PRECISION, date TIMESTAMP);"""

# insert the values into PostgreSQL table
INSERT_INTO_VAL = """INSERT INTO val (gaussian_cnumber, threshold, date) VALUES (%s, %s, %s);"""


# define an empty list for threshold and n_component values
values = []

# create an api object and app
app = Flask(__name__)
api = Api(app)
# creating HTTPBasicAuthentication object as auth
auth = HTTPBasicAuth()

# define username and password
USER_DATA = {
    "CAVDAR" : "password"
}

# error handling for Bad Request (400)
@app.errorhandler(400)
def handle_400_error(_error):
    return make_response(jsonify({"error" : "VERY VERY BAD REQUEST"}), 400)

# error handling for Not Found (404)
@app.errorhandler(404)
def handle_404_error(_error):
    return make_response(jsonify({"error" : "THERE IS NOTHING TO SEE!!"}), 404)
    
# error handling for Method Not Allowed (405)
@app.errorhandler(405)
def handle_405_error(_error):
    return make_response(jsonify({"error" : "THIS METHOD IS NOT ALLOWED"}), 405)

@app.errorhandler(500)
def handle_500_error(_error):
    return make_response(jsonify({"error" : "INTERNAL SERVER ERROR"}), 500)

# verifying password for HTTPBasicAuthentication
@auth.verify_password
def verify(username, password):
    if not(username and password):
        return False
    return USER_DATA.get(username) == password

# get method for getting raw data from postman
@app.route("/get", methods = ["GET"]) # type: ignore
@auth.login_required
def get():
    request_data = request.get_json()
    if request_data is not None:
        return({"data" : request_data["data"]})
    else:
        return(make_response(jsonify({"error" : "NO DATA FOUND"}), 400))

    
# Posting raw data from postman and insert into PostgreSQL
@app.route("/post_data", methods = ["POST"])
@auth.login_required
def post():
    if request.is_json:
        try:
            request_data = request.get_json()
            if request_data is not None:
                data = {
                    'data': request_data['data']
                }
            else:
                return(make_response(jsonify({"error" : "NO DATA FOUND"}), 400))
            my_data = pd.DataFrame.from_dict(data)
            thresh, n_opt, _, _, _ = gauss_m_m(my_data)

            gaussian_cnumber = n_opt
            threshold = thresh
            utc_now = datetime.utcnow()
            utc = pytz.timezone('UTC')
            aware_date = utc.localize(utc_now)
            turkey = timezone('Europe/Istanbul')
            date = aware_date.astimezone(turkey).replace(tzinfo=None)
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(CREATE_VAL_TABLE)
                    cursor.execute(INSERT_INTO_VAL, (gaussian_cnumber, threshold, date))

            return {"threshold value" : thresh,
                    "optimum gaussian component number": n_opt}
        except ValueError:
            return jsonify({"error" : "ValueError : Check your data"})
        except KeyError:
            return jsonify({"error" : "KeyError : Invalid request data"})
        except Exception:
            return jsonify({"error" : "An error occurred"})
    else:
        return jsonify({"message" : "Given data is not json"})

@app.route("/post_manually", methods = ["POST"])
@auth.login_required
def post_manual():
    if request.is_json:
        try:
            data = request.get_json()
            gaussian_cnumber = data['gaussian_cnumber']
            threshold = data['threshold']
            date = datetime.now()
            
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(CREATE_VAL_TABLE)
                    cursor.execute(INSERT_INTO_VAL, (gaussian_cnumber, threshold, date))
                    
            return jsonify({"threshold value" : threshold,
                            "gaussian_cnumber" : gaussian_cnumber})
        except ValueError:
                return jsonify({"error" : "ValueError : Check your data"})
        except KeyError:
            return jsonify({"error" : "KeyError : Invalid request data"})
        except Exception:
            return jsonify({"error" : "An error occurred"})
    else:
        return jsonify({"message" : "Given data is not json"})
        

# run the app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
