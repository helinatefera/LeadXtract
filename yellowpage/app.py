import csv
from io import StringIO

from flask import Flask, make_response, render_template, request

app = Flask(__name__)
from scraper import YellowPageScraper


@app.route("/")
def form():
    return render_template("./form.html")


@app.route("/download", methods=["POST"])
def download():
    # Retrieve data from form
    business = request.form["business"]
    location = request.form["location"]

    yellowpage = YellowPageScraper(business, location)
    data = yellowpage.scrape()
    cols = ["business_name", "categories", "phone_number", "street_address", "locality"]

    si = StringIO()
    cw = csv.writer(si)
    cw.writerows([cols] + data)
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export.csv"
    output.headers["Content-type"] = "text/csv"
    return output


if __name__ == "__main__":
    app.run(debug=True)
