from flask import Flask, render_template, request, url_for, Markup, jsonify,make_response
import pickle
import pandas as pd
import numpy as np
from werkzeug.utils import secure_filename
import joblib
from app import app
import subprocess


#Deserializing ml models
kmeanclus = pickle.load(open('./Prediction/kmean.pkl','rb'))
kprotoclus = joblib.load('./Prediction/kproto.pkl')
rdcls = joblib.load('./Prediction/cls.pkl')
lr = joblib.load('./Prediction/models.pkl')

#Exponential Smoothing
class ExponentialSmoothing:
    def __init__(self, alpha):
        self.alpha = alpha
        
    def fit(self, data):
        self.data = data
    
    def predict(self, year):
        # Apply exponential smoothing to the data
        smoothed_data = [self.data[0]]
        for i in range(1, len(self.data)):
            smoothed_data.append(self.alpha * self.data[i] + (1 - self.alpha) * smoothed_data[i-1])
        
        # Predict the value for the specified year using the smoothed data
        if year < len(self.data):
            return smoothed_data[year]
        else:
            last_value = smoothed_data[-1]
            for i in range(len(self.data), year):
                last_value = self.alpha * self.data[-1] + (1 - self.alpha) * last_value
            return last_value

#Population Projection Formula using Geometric Growth Method(Assump : Const Growth rate):
import math
def projection(v1,v2,yr1,yr2,year):
    t = yr2 - yr1
    n = year - yr2
    r = math.pow(v2/v1,1/t) - 1
    P = v2 * math.pow(1 + r,n)
    return P

@app.route('/')

#home:
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('About.html')

@app.route('/feedback')
def feedback():
    return render_template('Feedback.html')


#kmeans:
@app.route('/Kmeans')
def Kmeans():
 	return render_template("K-Means.html")

@app.route('/KMeansanalysis',methods=['POST'])
def KMeansanalysis():
    features = [x for x in request.form.values()]
    #Reading labelled and scaled data :
    df = pd.read_csv("Datasets/kmeansflask2.csv")
    years = df.loc[df["STATE/UT"]==features[0].upper()].loc[df["DISTRICT"]==features[1]]['YEAR'].values
    clusters = []
    for i in years:
        l = df.loc[df["STATE/UT"]==features[0].upper()].loc[df["DISTRICT"]==features[1]].loc[df["YEAR"]==i].values
        final_features = [[x for x in l[0] if type(x) == float]]
        y_pred = kmeanclus.predict(final_features)
        clusters.append(y_pred[0]) # 0-high,1-low,2-moderate
    #Finding Mode :
    high = 0
    low = 0
    moderate = 0
    for i in clusters:
        if i == 0:
            high += 1
        elif i == 1:
            low += 1
        else:
            moderate += 1
    if high > low and high > moderate:         
        label="RED ZONE"
    elif low > high and low > moderate:
        label="GREEN ZONE"
    elif moderate > high and moderate > low:
        label = "ORANGE ZONE"
    else:
        if high == moderate == low:
            label = "Crime Rate Varies a Lot"
        elif high == moderate:
            label = "Red-Orange Zone(Lies between Orange Zone and Red Zone)"
        elif low == moderate:
            label = "Yellow Zone(Lies between Green Zone and Orange Zone)"
        else:
            label = "Crime Rate Varies a Lot"

    return render_template('K-Means.html',prediction_text0 = label)


#RandomForest:
@app.route('/Randomfrstcls')
def Randomfrstcls():
 	return render_template("RandomForestClassifer.html")

@app.route('/randomfrstcls',methods=['POST'])
def randomfrstcls():
    features = [[x for x in request.form.values()]]
    unlabelled = [features[0][0],features[0][1]]
    df = pd.read_csv("Datasets/encoded.csv")
    arr = df.loc[df["STATE/UT"] == features[0][0].upper()].loc[df["DISTRICT"] == features[0][1]].values
    features[0][0] = arr[0][3]
    features[0][1] = arr[0][4]
    features[0][2] = int(features[0][2])
    df1 = pd.read_csv("Datasets/classfication_data_with_cluster_labels.csv")
    df1.drop(["Unnamed: 0"],axis=1,inplace=True)
    crimes = df1.columns[3:11]
    t = features[0][2] - df1.loc[df1["STATE/UT"]==features[0][0]].loc[df1["DISTRICT"]==features[0][1]]['YEAR'].values[-1]
    obj = ExponentialSmoothing(0.3)
    final_features = []
    final_features += features[0]
    for i in crimes:
        l = df1.loc[df1["STATE/UT"]==features[0][0]].loc[df1["DISTRICT"]==features[0][1]][i].values
        obj.fit(l)
        final_features.append(int(obj.predict(t)))
    final_features = pd.DataFrame([final_features])
    y_pred = rdcls.predict(final_features)
    if y_pred[0] == 1:         
        label="RED ZONE"
    elif y_pred[0] == 2:
        label="GREEN ZONE"
    elif y_pred[0] == 3:
        label = "ORANGE ZONE"
    final_features[0] = unlabelled[0]
    final_features[1] = unlabelled[1]
    return render_template("RandomForestClassifer.html",prediction_text = label + ' ' + str(list(final_features.values)))

#LinearRegression:
@app.route('/LinearReg')
def LinearReg():
 	return render_template("linear-regression.html")

@app.route('/linearreg',methods=["POST"])
def linearreg():
    features = [x for x in request.form.values()]
    df = pd.read_csv("Datasets/data.csv")
    a1 = list(df.loc[df["State/UT"]==features[0]]['Population (in lakhs)'].values)[0]
    a2 = list(df.loc[df["State/UT"]==features[0]]['Population (in lakhs)'].values)[-1]
    y1 = list(df.loc[df["State/UT"]==features[0]]['Year'].values)[0]
    y2 = list(df.loc[df["State/UT"]==features[0]]['Year'].values)[-1]
    estimated_population = projection(a1,a2,y1,y2,int(features[1]))
    y_pred = lr[features[0]].predict(pd.DataFrame([[int(estimated_population)]]))
    return render_template("linear-regression.html",prediction_text = 'Total IPC Crimes Y: ' + str(int(y_pred[0][0])) + ', Projected Population(in Lakhs) X: ' + str(int(estimated_population)) + ', Crime Rate: ' + str(int(y_pred[0][0] / estimated_population)))

# time series forecasting pages missing for crime rate, ipc
@app.route('/timeseriesipc')
def timeseriesipc():
    return render_template('total-ipc-forecasting.html')

@app.route('/timeseriescr')
def timeseriescr():
    return render_template('time-series-forcasting.html')

#Google charts:
@app.route('/analysis')
def analysis():
    return render_template('Analysis.html') #google charts

#crimefeed:
@app.route('/crimefeed')
def crimefeed():
    response = make_response('templates/final.html')
    
    # Add cache-control headers to prevent caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return render_template('crimefeed.html')


#Plotly charts:
@app.route('/analysis2')
def analysis2():
    return render_template('Analysis2.html') #plotly charts

#Geospatial analysis:
@app.route('/analysis3')
def analysis3():
    return render_template('Analysis3(maps).html') #geospatial analysis

#Data display:
@app.route('/datadisp')
def datadisp():
    return render_template('datadisplay.html')
#Heat Map:
@app.route('/foliummap')
def foliummap():
 	return render_template("final.html")

@app.route("/run-file")
def run_file():
    file_path = "folium-map\index.py"  
    subprocess.Popen(["python", file_path])
    return {"message": "File execution initiated"}


# defining paths to plotly graphs

@app.route('/plots/Multi_linear/Andhra Pradesh_linear.html')
def g1():
    return render_template('plots/Multi_linear/Andhra Pradesh_linear.html')
    
@app.route('/plots/Multi_linear/Arunachal Pradesh_linear.html')
def g2():
    return render_template('plots/Multi_linear/Arunachal Pradesh_linear.html')
    
@app.route('/plots/Multi_linear/Assam_linear.html')
def g3():
    return render_template('plots/Multi_linear/Assam_linear.html')
    
@app.route('/plots/Multi_linear/Bihar_linear.html')
def g4():
    return render_template('plots/Multi_linear/Bihar_linear.html')
    
@app.route('/plots/Multi_linear/Chhatisgarh_linear.html')
def g5():
    return render_template('plots/Multi_linear/Chhatisgarh_linear.html')
    
@app.route('/plots/Multi_linear/Goa_linear.html')
def g6():
    return render_template('plots/Multi_linear/Goa_linear.html')
    
@app.route('/plots/Multi_linear/Gujrat_linear.html')
def g7():
    return render_template('plots/Multi_linear/Gujrat_linear.html')
    
@app.route('/plots/Multi_linear/Haryana_linear.html')
def g8():
    return render_template('plots/Multi_linear/Haryana_linear.html')
    
@app.route('/plots/Multi_linear/Himachal Pradesh_linear.html')
def g9():
    return render_template('plots/Multi_linear/Himachal Pradesh_linear.html')
    
@app.route('/plots/Multi_linear/Jammu & Kashmir_linear.html')
def g10():
    return render_template('plots/Multi_linear/Jammu & Kashmir_linear.html')
    
@app.route('/plots/Multi_linear/Jharkhand_linear.html')
def g11():
    return render_template('plots/Multi_linear/Jharkhand_linear.html')
    
@app.route('/plots/Multi_linear/Karnataka_linear.html')
def g12():
    return render_template('plots/Multi_linear/Karnataka_linear.html')
    
@app.route('/plots/Multi_linear/Kerala_linear.html')
def g13():
    return render_template('plots/Multi_linear/kerala_linear.html')
    
@app.route('/plots/Multi_linear/Madhya Pradesh_linear.html')
def g14():
    return render_template('plots/Multi_linear/Madhya Pradesh_linear.html')
    
@app.route('/plots/Multi_linear/Maharashtra_linear.html')
def g15():
    return render_template('plots/Multi_linear/Maharashtra_linear.html')
    
@app.route('/plots/Multi_linear/Manipur_linear.html')
def g16():
    return render_template('plots/Multi_linear/Manipur_linear.html')
    
@app.route('/plots/Multi_linear/Meghalaya_linear.html')
def g17():
    return render_template('plots/Multi_linear/Meghalaya_linear.html')
    
@app.route('/plots/Multi_linear/Mizoram_linear.html')
def g18():
    return render_template('plots/Multi_linear/Mizoram_linear.html')
    
@app.route('/plots/Multi_linear/Nagaland_linear.html')
def g19():
    return render_template('plots/Multi_linear/Nagaland_linear.html')
    
@app.route('/plots/Multi_linear/Odisha_linear.html')
def g20():
    return render_template('plots/Multi_linear/Odisha_linear.html')
    
@app.route('/plots/Multi_linear/Punjab_linear.html')
def g21():
    return render_template('plots/Multi_linear/Punjab_linear.html')
    
@app.route('/plots/Multi_linear/Sikkim_linear.html')
def g22():
    return render_template('plots/Multi_linear/Sikkim_linear.html')
    
@app.route('/plots/Multi_linear/Tamil Nadu_linear.html')
def g23():
    return render_template('plots/Multi_linear/Tamil Nadu_linear.html')
    
@app.route('/plots/Multi_linear/Telangana_linear.html')
def g24():
    return render_template('plots/Multi_linear/Telangana_linear.html')
    
@app.route('/plots/Multi_linear/Tripura_linear.html')
def g25():
    return render_template('plots/Multi_linear/Tripura_linear.html')
    
@app.route('/plots/Multi_linear/Uttar Pradesh_linear.html')
def g26():
    return render_template('plots/Multi_linear/Uttar Pradesh_linear.html')
    
@app.route('/plots/Multi_linear/Uttaranchal_linear.html')
def g27():
    return render_template('plots/Multi_linear/Uttaranchal_linear.html')
    
@app.route('/plots/Multi_linear/West Bengal_linear.html')
def g28():
    return render_template('plots/Multi_linear/West Bengal_linear.html')
    
@app.route('/plots/Multi_linear/A & N Islands_linear.html')
def g29():
    return render_template('plots/Multi_linear/A & N Islands_linear.html')
    
@app.route('/plots/Multi_linear/Chandigarh_linear.html')
def g30():
    return render_template('plots/Multi_linear/Chandigarh_linear.html')
    
@app.route('/plots/Multi_linear/D & N Haveli and Daman & Diu_linear.html')
def g31():
    return render_template('plots/Multi_linear/D & N Haveli and Daman & Diu_linear.html')

@app.route('/plots/Multi_linear/Delhi_linear.html')
def g32():
    return render_template('plots/Multi_linear/Delhi_linear.html')
    
@app.route('/plots/Multi_linear/Lakshadweep_linear.html')
def g33():
    return render_template('plots/Multi_linear/Lakshadweep_linear.html')
    
@app.route('/plots/Multi_linear/Puducherry_linear.html')
def g34():
    return render_template('plots/Multi_linear/Pudducherry_linear.html')
    
@app.route('/plots/Multi_linear/Rajasthan_linear.html')
def g35():
    return render_template('plots/Multi_linear/Rajasthan_linear.html')
    
@app.route('/plots/Multi_linear/Assam_linear.html')
def g36():
    return render_template('plots/Multi_linear/Assam_linear.html')

@app.route('/plots/Stacked_Bar_Charts/Andhra Pradesh_stbar.html')
def g37():
    return render_template('plots/Stacked_Bar_Charts/Andhra Pradesh_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Arunachal Pradesh_stbar.html')
def g38():
    return render_template('plots/Stacked_Bar_Charts/Arunachal Pradesh_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Assam_stbar.html')
def g39():
    return render_template('plots/Stacked_Bar_Charts/Assam_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Bihar_stbar.html')
def g40():
    return render_template('plots/Stacked_Bar_Charts/Bihar_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Chhatisgarh_stbar.html')
def g41():
    return render_template('plots/Stacked_Bar_Charts/Chhatisgarh_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Goa_stbar.html')
def g42():
    return render_template('plots/Stacked_Bar_Charts/Goa_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Gujrat_stbar.html')
def g43():
    return render_template('plots/Stacked_Bar_Charts/Gujrat_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Haryana_stbar.html')
def g44():
    return render_template('plots/Stacked_Bar_Charts/Haryana_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Himachal Pradesh_stbar.html')
def g45():
    return render_template('plots/Stacked_Bar_Charts/Himachal Pradesh_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Jammu & Kashmir_stbar.html')
def g46():
    return render_template('plots/Stacked_Bar_Charts/Jammu & Kashmir_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Jharkhand_stbar.html')
def g47():
    return render_template('plots/Stacked_Bar_Charts/Jharkhand_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Karnataka_stbar.html')
def g48():
    return render_template('plots/Stacked_Bar_Charts/Karnataka_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Kerala_stbar.html')
def g49():
    return render_template('plots/Stacked_Bar_Charts/kerala_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Madhya Pradesh_stbar.html')
def g50():
    return render_template('plots/Stacked_Bar_Charts/Madhya Pradesh_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Maharashtra_stbar.html')
def g51():
    return render_template('plots/Stacked_Bar_Charts/Maharashtra_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Manipur_stbar.html')
def g52():
    return render_template('plots/Stacked_Bar_Charts/Manipur_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Meghalaya_stbar.html')
def g53():
    return render_template('plots/Stacked_Bar_Charts/Meghalaya_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Mizoram_stbar.html')
def g54():
    return render_template('plots/Stacked_Bar_Charts/Mizoram_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Nagaland_stbar.html')
def g55():
    return render_template('plots/Stacked_Bar_Charts/Nagaland_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Odisha_stbar.html')
def g56():
    return render_template('plots/Stacked_Bar_Charts/Odisha_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Punjab_stbar.html')
def g57():
    return render_template('plots/Stacked_Bar_Charts/Punjab_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Sikkim_stbar.html')
def g58():
    return render_template('plots/Stacked_Bar_Charts/Sikkim_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Tamil Nadu_stbar.html')
def g59():
    return render_template('plots/Stacked_Bar_Charts/Tamil Nadu_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Telangana_stbar.html')
def g60():
    return render_template('plots/Stacked_Bar_Charts/Telangana_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Tripura_stbar.html')
def g61():
    return render_template('plots/Stacked_Bar_Charts/Tripura_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Uttar Pradesh_stbar.html')
def g62():
    return render_template('plots/Stacked_Bar_Charts/Uttar Pradesh_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Uttaranchal_stbar.html')
def g63():
    return render_template('plots/Stacked_Bar_Charts/Uttaranchal_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/West Bengal_stbar.html')
def g64():
    return render_template('plots/Stacked_Bar_Charts/West Bengal_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/A & N Islands_stbar.html')
def g65():
    return render_template('plots/Stacked_Bar_Charts/A & N Islands_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Chandigarh_stbar.html')
def g66():
    return render_template('plots/Stacked_Bar_Charts/Chandigarh_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/D & N Haveli and Daman & Diu_stbar.html')
def g67():
    return render_template('plots/Stacked_Bar_Charts/D & N Haveli and Daman & Diu_stbar.html')

@app.route('/plots/Stacked_Bar_Charts/Delhi_stbar.html')
def g68():
    return render_template('plots/Stacked_Bar_Charts/Delhi_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Lakshadweep_stbar.html')
def g69():
    return render_template('plots/Stacked_Bar_Charts/Lakshadweep_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Puducherry_stbar.html')
def g70():
    return render_template('plots/Stacked_Bar_Charts/Pudducherry_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Rajasthan_stbar.html')
def g71():
    return render_template('plots/Stacked_Bar_Charts/Rajasthan_stbar.html')
    
@app.route('/plots/Stacked_Bar_Charts/Assam_stbar.html')
def g72():
    return render_template('plots/Stacked_Bar_Charts/Assam_stbar.html')

@app.route('/plots/Grouped_Bar_Charts/Andhra Pradesh_grbar.html')
def g73():
    return render_template('plots/Grouped_Bar_Charts/Andhra Pradesh_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Arunachal Pradesh_grbar.html')
def g74():
    return render_template('plots/Grouped_Bar_Charts/Arunachal Pradesh_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Assam_grbar.html')
def g75():
    return render_template('plots/Grouped_Bar_Charts/Assam_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Bihar_grbar.html')
def g76():
    return render_template('plots/Grouped_Bar_Charts/Bihar_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Chhatisgarh_grbar.html')
def g77():
    return render_template('plots/Grouped_Bar_Charts/Chhatisgarh_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Goa_grbar.html')
def g78():
    return render_template('plots/Grouped_Bar_Charts/Goa_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Gujrat_grbar.html')
def g79():
    return render_template('plots/Grouped_Bar_Charts/Gujrat_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Haryana_grbar.html')
def g80():
    return render_template('plots/Grouped_Bar_Charts/Haryana_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Himachal Pradesh_grbar.html')
def g81():
    return render_template('plots/Grouped_Bar_Charts/Himachal Pradesh_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Jammu & Kashmir_grbar.html')
def g82():
    return render_template('plots/Grouped_Bar_Charts/Jammu & Kashmir_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Jharkhand_grbar.html')
def g83():
    return render_template('plots/Grouped_Bar_Charts/Jharkhand_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Karnataka_grbar.html')
def g84():
    return render_template('plots/Grouped_Bar_Charts/Karnataka_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Kerala_grbar.html')
def g85():
    return render_template('plots/Grouped_Bar_Charts/kerala_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Madhya Pradesh_grbar.html')
def g86():
    return render_template('plots/Grouped_Bar_Charts/Madhya Pradesh_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Maharashtra_grbar.html')
def g87():
    return render_template('plots/Grouped_Bar_Charts/Maharashtra_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Manipur_grbar.html')
def g88():
    return render_template('plots/Grouped_Bar_Charts/Manipur_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Meghalaya_grbar.html')
def g89():
    return render_template('plots/Grouped_Bar_Charts/Meghalaya_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Mizoram_grbar.html')
def g90():
    return render_template('plots/Grouped_Bar_Charts/Mizoram_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Nagaland_grbar.html')
def g91():
    return render_template('plots/Grouped_Bar_Charts/Nagaland_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Odisha_grbar.html')
def g92():
    return render_template('plots/Grouped_Bar_Charts/Odisha_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Punjab_grbar.html')
def g93():
    return render_template('plots/Grouped_Bar_Charts/Punjab_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Sikkim_grbar.html')
def g94():
    return render_template('plots/Grouped_Bar_Charts/Sikkim_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Tamil Nadu_grbar.html')
def g95():
    return render_template('plots/Grouped_Bar_Charts/Tamil Nadu_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Telangana_grbar.html')
def g96():
    return render_template('plots/Grouped_Bar_Charts/Telangana_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Tripura_grbar.html')
def g97():
    return render_template('plots/Grouped_Bar_Charts/Tripura_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Uttar Pradesh_grbar.html')
def g98():
    return render_template('plots/Grouped_Bar_Charts/Uttar Pradesh_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Uttaranchal_grbar.html')
def g99():
    return render_template('plots/Grouped_Bar_Charts/Uttaranchal_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/West Bengal_grbar.html')
def g100():
    return render_template('plots/Grouped_Bar_Charts/West Bengal_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/A & N Islands_grbar.html')
def g101():
    return render_template('plots/Grouped_Bar_Charts/A & N Islands_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Chandigarh_grbar.html')
def g102():
    return render_template('plots/Grouped_Bar_Charts/Chandigarh_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/D & N Haveli and Daman & Diu_grbar.html')
def g103():
    return render_template('plots/Grouped_Bar_Charts/D & N Haveli and Daman & Diu_grbar.html')

@app.route('/plots/Grouped_Bar_Charts/Delhi_grbar.html')
def g104():
    return render_template('plots/Grouped_Bar_Charts/Delhi_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Lakshadweep_grbar.html')
def g105():
    return render_template('plots/Grouped_Bar_Charts/Lakshadweep_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Puducherry_grbar.html')
def g106():
    return render_template('plots/Grouped_Bar_Charts/Pudducherry_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Rajasthan_grbar.html')
def g107():
    return render_template('plots/Grouped_Bar_Charts/Rajasthan_grbar.html')
    
@app.route('/plots/Grouped_Bar_Charts/Assam_grbar.html')
def g108():
    return render_template('plots/Grouped_Bar_Charts/Assam_grbar.html')
    
#Geospatial links :
@app.route('/plots/Choropleth/2014/2014_Corruption.html')
def m1():
    return render_template('plots/Choropleth/2014/2014_Corruption.html')
@app.route('/plots/Choropleth/2014/2014_Crimes_Against_Children.html')
def m2():
    return render_template('plots/Choropleth/2014/2014_Crimes_Against_Children.html')
@app.route('/plots/Choropleth/2014/2014_Crimes_Against_Senior_Citizen.html')
def m3():
    return render_template('plots/Choropleth/2014/2014_Crimes_Against_Senior_Citizen.html')
@app.route('/plots/Choropleth/2014/2014_Crimes_Against_Women.html')
def m4():
    return render_template('plots/Choropleth/2014/2014_Crimes_Against_Women.html')
@app.route('/plots/Choropleth/2014/2014_Cyber_Crime.html')
def m5():
    return render_template('plots/Choropleth/2014/2014_Cyber_Crime.html')
@app.route('/plots/Choropleth/2014/2014_Kidnapping.html')
def m6():
    return render_template('plots/Choropleth/2014/2014_Kidnapping.html')
@app.route('/plots/Choropleth/2014/2014_Murders.html')
def m7():
    return render_template('plots/Choropleth/2014/2014_Murders.html')
@app.route('/plots/Choropleth/2014/2014_Total_Crimes.html')
def m8():
    return render_template('plots/Choropleth/2014/2014_Total_Crimes.html')
@app.route('/plots/Choropleth/2015/2015_Corruption.html')
def m9():
    return render_template('plots/Choropleth/2015/2015_Corruption.html')
@app.route('/plots/Choropleth/2015/2015_Crimes_Against_Children.html')
def m10():
    return render_template('plots/Choropleth/2015/2015_Crimes_Against_Children.html')
@app.route('/plots/Choropleth/2015/2015_Crimes_Against_Senior_Citizen.html')
def m11():
    return render_template('plots/Choropleth/2015/2015_Crimes_Against_Senior_Citizen.html')
@app.route('/plots/Choropleth/2015/2015_Crimes_Against_Women.html')
def m12():
    return render_template('plots/Choropleth/2015/2015_Crimes_Against_Women.html')
@app.route('/plots/Choropleth/2015/2015_Cyber_Crime.html')
def m13():
    return render_template('plots/Choropleth/2015/2015_Cyber_Crime.html')
@app.route('/plots/Choropleth/2015/2015_Kidnapping.html')
def m14():
    return render_template('plots/Choropleth/2015/2015_Kidnapping.html')
@app.route('/plots/Choropleth/2015/2015_Murders.html')
def m15():
    return render_template('plots/Choropleth/2015/2015_Murders.html')
@app.route('/plots/Choropleth/2015/2015_Total_Crimes.html')
def m16():
    return render_template('plots/Choropleth/2015/2015_Total_Crimes.html')
@app.route('/plots/Choropleth/2016/2016_Corruption.html')
def m17():
    return render_template('plots/Choropleth/2016/2016_Corruption.html')
@app.route('/plots/Choropleth/2016/2016_Crimes_Against_Children.html')
def m18():
    return render_template('plots/Choropleth/2016/2016_Crimes_Against_Children.html')
@app.route('/plots/Choropleth/2016/2016_Crimes_Against_Senior_Citizen.html')
def m19():
    return render_template('plots/Choropleth/2016/2016_Crimes_Against_Senior_Citizen.html')
@app.route('/plots/Choropleth/2016/2016_Crimes_Against_Women.html')
def m20():
    return render_template('plots/Choropleth/2016/2016_Crimes_Against_Women.html')
@app.route('/plots/Choropleth/2016/2016_Cyber_Crime.html')
def m21():
    return render_template('plots/Choropleth/2016/2016_Cyber_Crime.html')
@app.route('/plots/Choropleth/2016/2016_Kidnapping.html')
def m22():
    return render_template('plots/Choropleth/2016/2016_Kidnapping.html')
@app.route('/plots/Choropleth/2016/2016_Murders.html')
def m23():
    return render_template('plots/Choropleth/2016/2016_Murders.html')
@app.route('/plots/Choropleth/2016/2016_Total_Crimes.html')
def m24():
    return render_template('plots/Choropleth/2016/2016_Total_Crimes.html')
@app.route('/plots/Choropleth/2017/2017_Corruption.html')
def m25():
    return render_template('plots/Choropleth/2017/2017_Corruption.html')
@app.route('/plots/Choropleth/2017/2017_Crimes_Against_Children.html')
def m26():
    return render_template('plots/Choropleth/2017/2017_Crimes_Against_Children.html')
@app.route('/plots/Choropleth/2017/2017_Crimes_Against_Senior_Citizen.html')
def m27():
    return render_template('plots/Choropleth/2017/2017_Crimes_Against_Senior_Citizen.html')
@app.route('/plots/Choropleth/2017/2017_Crimes_Against_Women.html')
def m28():
    return render_template('plots/Choropleth/2017/2017_Crimes_Against_Women.html')
@app.route('/plots/Choropleth/2017/2017_Cyber_Crime.html')
def m29():
    return render_template('plots/Choropleth/2017/2017_Cyber_Crime.html')
@app.route('/plots/Choropleth/2017/2017_Kidnapping.html')
def m30():
    return render_template('plots/Choropleth/2017/2017_Kidnapping.html')
@app.route('/plots/Choropleth/2017/2017_Murders.html')
def m31():
    return render_template('plots/Choropleth/2017/2017_Murders.html')
@app.route('/plots/Choropleth/2017/2017_Total_Crimes.html')
def m32():
    return render_template('plots/Choropleth/2017/2017_Total_Crimes.html')
@app.route('/plots/Choropleth/2018/2018_Corruption.html')
def m33():
    return render_template('plots/Choropleth/2018/2018_Corruption.html')
@app.route('/plots/Choropleth/2018/2018_Crimes_Against_Children.html')
def m34():
    return render_template('plots/Choropleth/2018/2018_Crimes_Against_Children.html')
@app.route('/plots/Choropleth/2018/2018_Crimes_Against_Senior_Citizen.html')
def m35():
    return render_template('plots/Choropleth/2018/2018_Crimes_Against_Senior_Citizen.html')
@app.route('/plots/Choropleth/2018/2018_Crimes_Against_Women.html')
def m36():
    return render_template('plots/Choropleth/2018/2018_Crimes_Against_Women.html')
@app.route('/plots/Choropleth/2018/2018_Cyber_Crime.html')
def m37():
    return render_template('plots/Choropleth/2018/2018_Cyber_Crime.html')
@app.route('/plots/Choropleth/2018/2018_Kidnapping.html')
def m38():
    return render_template('plots/Choropleth/2018/2018_Kidnapping.html')
@app.route('/plots/Choropleth/2018/2018_Murders.html')
def m39():
    return render_template('plots/Choropleth/2018/2018_Murders.html')
@app.route('/plots/Choropleth/2018/2018_Total_Crimes.html')
def m40():
    return render_template('plots/Choropleth/2018/2018_Total_Crimes.html')
@app.route('/plots/Choropleth/2019/2019_Corruption.html')
def m41():
    return render_template('plots/Choropleth/2019/2019_Corruption.html')
@app.route('/plots/Choropleth/2019/2019_Crimes_Against_Children.html')
def m42():
    return render_template('plots/Choropleth/2019/2019_Crimes_Against_Children.html')
@app.route('/plots/Choropleth/2019/2019_Crimes_Against_Senior_Citizen.html')
def m43():
    return render_template('plots/Choropleth/2019/2019_Crimes_Against_Senior_Citizen.html')
@app.route('/plots/Choropleth/2019/2019_Crimes_Against_Women.html')
def m44():
    return render_template('plots/Choropleth/2019/2019_Crimes_Against_Women.html')
@app.route('/plots/Choropleth/2019/2019_Cyber_Crime.html')
def m45():
    return render_template('plots/Choropleth/2019/2019_Cyber_Crime.html')
@app.route('/plots/Choropleth/2019/2019_Kidnapping.html')
def m46():
    return render_template('plots/Choropleth/2019/2019_Kidnapping.html')
@app.route('/plots/Choropleth/2019/2019_Murders.html')
def m47():
    return render_template('plots/Choropleth/2019/2019_Murders.html')
@app.route('/plots/Choropleth/2019/2019_Total_Crimes.html')
def m48():
    return render_template('plots/Choropleth/2019/2019_Total_Crimes.html')
@app.route('/plots/Choropleth/2020/2020_Corruption.html')
def m49():
    return render_template('plots/Choropleth/2020/2020_Corruption.html')
@app.route('/plots/Choropleth/2020/2020_Crimes_Against_Children.html')
def m50():
    return render_template('plots/Choropleth/2020/2020_Crimes_Against_Children.html')
@app.route('/plots/Choropleth/2020/2020_Crimes_Against_Senior_Citizen.html')
def m51():
    return render_template('plots/Choropleth/2020/2020_Crimes_Against_Senior_Citizen.html')
@app.route('/plots/Choropleth/2020/2020_Crimes_Against_Women.html')
def m52():
    return render_template('plots/Choropleth/2020/2020_Crimes_Against_Women.html')
@app.route('/plots/Choropleth/2020/2020_Cyber_Crime.html')
def m53():
    return render_template('plots/Choropleth/2020/2020_Cyber_Crime.html')
@app.route('/plots/Choropleth/2020/2020_Kidnapping.html')
def m54():
    return render_template('plots/Choropleth/2020/2020_Kidnapping.html')
@app.route('/plots/Choropleth/2020/2020_Murders.html')
def m55():
    return render_template('plots/Choropleth/2020/2020_Murders.html')
@app.route('/plots/Choropleth/2020/2020_Total_Crimes.html')
def m56():
    return render_template('plots/Choropleth/2020/2020_Total_Crimes.html')
@app.route('/plots/Choropleth/2021/2021_Corruption.html')
def m57():
    return render_template('plots/Choropleth/2021/2021_Corruption.html')
@app.route('/plots/Choropleth/2021/2021_Crimes_Against_Children.html')
def m58():
    return render_template('plots/Choropleth/2021/2021_Crimes_Against_Children.html')
@app.route('/plots/Choropleth/2021/2021_Crimes_Against_Senior_Citizen.html')
def m59():
    return render_template('plots/Choropleth/2021/2021_Crimes_Against_Senior_Citizen.html')
@app.route('/plots/Choropleth/2021/2021_Crimes_Against_Women.html')
def m60():
    return render_template('plots/Choropleth/2021/2021_Crimes_Against_Women.html')
@app.route('/plots/Choropleth/2021/2021_Cyber_Crime.html')
def m61():
    return render_template('plots/Choropleth/2021/2021_Cyber_Crime.html')
@app.route('/plots/Choropleth/2021/2021_Kidnapping.html')
def m62():
    return render_template('plots/Choropleth/2021/2021_Kidnapping.html')
@app.route('/plots/Choropleth/2021/2021_Murders.html')
def m63():
    return render_template('plots/Choropleth/2021/2021_Murders.html')
@app.route('/plots/Choropleth/2021/2021_Total_Crimes.html')
def m64():
    return render_template('plots/Choropleth/2021/2021_Total_Crimes.html')

