from flask import Flask, render_template, request, send_file, jsonify
import requests
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
from datetime import datetime
import io

app = Flask(__name__)

# ---------------------------
# 1. KOSPI 종목 리스트 가져오기
# ---------------------------
def get_kospi_list():
    base_url = "https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page={}"
    headers = {"User-Agent": "Mozilla/5.0"}
    #res = requests.get(url, headers=headers)
    #soup = BeautifulSoup(res.text, "html.parser")

    stocks = []
    
    for page in range(1, 2):
        url = base_url.format(page)
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.select("table.type_2 tbody tr")

        for row in rows:
            name_tag = row.select_one("a.tltle")
            price_tag = row.select_one("td:nth-child(3)")

            if name_tag and price_tag:
                name = name_tag.text.strip()
                code = name_tag["href"].split("=")[-1]
                price = price_tag.text.strip().replace(",", "")

                stocks.append((name, code, float(price)))

    return stocks


# ---------------------------
# 2. 데이터 계산 함수
# ---------------------------

def calculate_data(date_input):
    stocks = get_kospi_list()[:200]

    input_date = pd.to_datetime(date_input)

    tickers = [code + ".KS" for name, code, price in stocks]
    name_map = {code + ".KS": name for name, code, price in stocks}
    current_price_map = {code + ".KS": price for name, code, price in stocks}

    df = yf.download(
        tickers,
        start=str(input_date.year) + "-01-01",
        progress=False,
        group_by="ticker",
        auto_adjust=False
    )

    results = []

    for ticker in tickers:

        try:
            data = df[ticker]

            if data.empty:
                continue

            data.index = pd.to_datetime(data.index)

            current_price = float(current_price_map[ticker])

            if input_date in data.index:
                input_close = float(data.loc[input_date, "Close"])
            else:
                prev_dates = data.index[data.index < input_date]
                if len(prev_dates) == 0:
                    continue
                input_close = float(data.loc[prev_dates[-1], "Close"])

            year_high = float(data["Close"].max())

            diff_input = round((current_price - input_close) / current_price * 100, 2)
            diff_year_high_ratio = round(
                (current_price - year_high) / year_high * 100, 2
            )

            results.append({
                "name": name_map[ticker],
                "current": round(current_price, 2),
                "input_close": round(input_close, 2),
                "diff_input": diff_input,
                "year_high": round(year_high, 2),
                "diff_year_high_ratio": diff_year_high_ratio
            })

        except:
            continue

    return results


# ---------------------------
# 3. 웹 라우팅
# ---------------------------
last_data = None   # 마지막 조회 결과 저장

@app.route("/", methods=["GET", "POST"])
def index():
    global last_data
    data = None

    if request.method == "POST":
        date_input = request.form["date"]
        data = calculate_data(date_input)
        last_data = data

    return render_template("index.html", data=data)

# ---------------------------
# 3. 엑셀 저장
# ---------------------------
@app.route("/download")
def download_excel():
    global last_data

    df = pd.DataFrame(last_data)

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        download_name="kospi_result.xlsx",
        as_attachment=True
    )

# ---------------------------
# 
# ---------------------------
@app.route("/api/kospi")
def api_kospi():

    date_input = request.args.get("date")

    if not date_input:
        return jsonify({"error": "date required"}), 400

    data = calculate_data(date_input)

    return jsonify(data)

# ---------------------------
# 4. 실행
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
