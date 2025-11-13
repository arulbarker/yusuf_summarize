# Deployment Guide untuk Vercel

## 🚀 Cara Deploy ke Vercel

### 1. Push ke GitHub
```bash
git add .
git commit -m "Setup for Vercel deployment with DeepSeek AI"
git push -u origin main
```

### 2. Deploy di Vercel

1. Buka [Vercel Dashboard](https://vercel.com/dashboard)
2. Klik **"Add New Project"**
3. Import repository GitHub: `https://github.com/arulbarker/yusuf_summarize.git`
4. Vercel akan otomatis mendeteksi konfigurasi

### 3. Setup Environment Variables

Di Vercel Dashboard, tambahkan environment variable berikut:

```
DEEPSEEK_API_KEY=sk-36fca51fd07e4382a5d6e627955613ed
```

**Cara menambahkan:**
1. Pilih project Anda di Vercel Dashboard
2. Klik **Settings** → **Environment Variables**
3. Tambahkan variable:
   - Name: `DEEPSEEK_API_KEY`
   - Value: `sk-36fca51fd07e4382a5d6e627955613ed`
4. Klik **Save**

### 4. Deploy

Setelah environment variables diset:
1. Kembali ke tab **Deployments**
2. Klik **Redeploy** jika perlu
3. Tunggu hingga deployment selesai (biasanya 1-2 menit)

### 5. Akses Aplikasi

Setelah deployment berhasil, aplikasi dapat diakses di:
- Production URL: `https://yusuf-summarize.vercel.app` (atau URL yang diberikan Vercel)

## 📝 Struktur Project untuk Vercel

```
YouSummarizer/
├── api/
│   └── get-video-details.py    # Serverless function untuk Vercel
├── index.html                    # Frontend aplikasi
├── vercel.json                   # Konfigurasi Vercel
├── requirements.txt              # Python dependencies
└── services/                     # Original Flask app (untuk local dev)
```

## 🔧 Testing Local

Untuk testing local sebelum deploy:

1. **Jalankan Flask server:**
```bash
cd services
python app.py
```

2. **Buka `simple_summarizer.html` atau `index.html` di browser**

## 🌐 API Endpoints

Setelah di-deploy, endpoint yang tersedia:

- `POST /api/get-video-details` - Summarize YouTube video
  - Body: `{ "video_url": "https://youtube.com/watch?v=..." }`
  - Response: `{ "title": "...", "summary": "...", "transcript": [...] }`

## ⚠️ Catatan Penting

1. **API Key Security**: Jangan hardcode API key di code yang di-push ke GitHub
2. **Rate Limits**: DeepSeek API mungkin memiliki rate limits
3. **Cold Start**: Serverless functions di Vercel mungkin memiliki cold start time
4. **Timeout**: Vercel free tier memiliki timeout 10 detik untuk serverless functions
5. **Video Length**: Video yang sangat panjang mungkin timeout atau memerlukan upgrade plan

## 🎯 Tips Deployment

- Selalu test local terlebih dahulu sebelum push
- Monitor Vercel logs untuk debugging
- Gunakan Vercel Analytics untuk tracking usage
- Set up custom domain jika diperlukan

## 📞 Support

Jika ada masalah deployment, check:
1. Vercel deployment logs
2. Browser console untuk frontend errors
3. Function logs di Vercel dashboard
