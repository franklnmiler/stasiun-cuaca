def get_air_quality_status(ppm):
    if ppm is None:
        return "Tidak diketahui"
    try:
        ppm = float(ppm)
    except:
        return "Tidak valid"

    if 0 <= ppm <= 80:
        return "Aman"
    elif 80 < ppm <= 100:
        return "Kurang Bersih"
    elif 100 < ppm <= 150:
        return "Tercemar"
    elif 150 < ppm <= 300:
        return "Polusi Berbahaya"
    elif 300 < ppm <= 999:
        return "Berbahaya Tinggi"
    else:
        return "Diluar Batas"
