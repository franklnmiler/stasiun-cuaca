const socket = io.connect('http://kelompok7.com:5002');

let suhuChart, kelembapanChart, tekananChart;

// Fungsi untuk membuat chart
function createChart(ctx, label, data, borderColor, bgColor, satuan) {
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: [{
        label: label,
        data: data.data,
        borderColor: borderColor,
        backgroundColor: bgColor,
        fill: true,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: 'Waktu' }},
        y: { title: { display: true, text: satuan }}
      }
    }
  });
}

// Fungsi untuk memperbarui tampilan data dan grafik
function updateCharts(data) {
  const waktu = new Date().toLocaleTimeString();
  const maxData = 20;

  // Update Ringkasan Data
  document.getElementById('suhu-terakhir').textContent = data.suhu + ' °C';
  document.getElementById('kelembapan-terakhir').textContent = data.kelembapan + ' %';
  document.getElementById('tekanan-terakhir').textContent = data.tekanan + ' hPa';
  document.getElementById('altitude-terakhir').textContent = data.altitude + ' m';
  document.getElementById('shcr04-jarak').textContent = data.jarak_ultrasonik + ' cm'; // ✅ Data Ultrasonik

  const kualitasUdara = `${data.mq135_ppm} ppm (${data.status_udara})`;
  document.getElementById('status-kualitas-udara').textContent = kualitasUdara;

  // Logika Deteksi Kebakaran
  let kebakaranStatus = '--';
  if (parseFloat(data.mq135_ppm) > 300) {
    kebakaranStatus = 'Bahaya';
  } else if (parseFloat(data.mq135_ppm) > 200) {
    kebakaranStatus = 'Waspada';
  } else {
    kebakaranStatus = 'Aman';
  }
  document.getElementById('kebakaran-terakhir').textContent = kebakaranStatus;

  // Update Chart Suhu
  if (suhuChart) {
    suhuChart.data.labels.push(waktu);
    suhuChart.data.datasets[0].data.push(data.suhu);
    if (suhuChart.data.labels.length > maxData) {
      suhuChart.data.labels.shift();
      suhuChart.data.datasets[0].data.shift();
    }
    suhuChart.update();
  }

  // Update Chart Kelembapan
  if (kelembapanChart) {
    kelembapanChart.data.labels.push(waktu);
    kelembapanChart.data.datasets[0].data.push(data.kelembapan);
    if (kelembapanChart.data.labels.length > maxData) {
      kelembapanChart.data.labels.shift();
      kelembapanChart.data.datasets[0].data.shift();
    }
    kelembapanChart.update();
  }

  // Update Chart Tekanan
  if (tekananChart) {
    tekananChart.data.labels.push(waktu);
    tekananChart.data.datasets[0].data.push(data.tekanan);
    if (tekananChart.data.labels.length > maxData) {
      tekananChart.data.labels.shift();
      tekananChart.data.datasets[0].data.shift();
    }
    tekananChart.update();
  }
}

// Load data awal ke chart dari API
async function loadSensorChart() {
  const res = await fetch('/api/bme280/chart-multi');
  const data = await res.json();

  suhuChart = createChart(
    document.getElementById('chart-suhu').getContext('2d'),
    'Suhu (°C)', { labels: data.labels, data: data.suhu },
    '#007bff', 'rgba(0,123,255,0.1)', '°C'
  );

  kelembapanChart = createChart(
    document.getElementById('chart-kelembapan').getContext('2d'),
    'Kelembapan (%)', { labels: data.labels, data: data.kelembapan },
    '#28a745', 'rgba(40,167,69,0.1)', '%'
  );

  tekananChart = createChart(
    document.getElementById('chart-tekanan').getContext('2d'),
    'Tekanan (hPa)', { labels: data.labels, data: data.tekanan },
    '#ffc107', 'rgba(255,193,7,0.1)', 'hPa'
  );
}

// Jalankan fungsi load saat halaman pertama kali dimuat
loadSensorChart();

// WebSocket listener untuk data baru
socket.on('new_data', function(data) {
  console.log('[WebSocket] Data Masuk:', data);
  updateCharts(data);
});
