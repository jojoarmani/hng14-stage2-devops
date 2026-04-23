const express = require('express');
const axios = require('axios');
const path = require('path');
const app = express();

// Fix: Use environment variable for API_URL (not hardcoded localhost)
const API_URL = process.env.API_URL || "http://api:8000";

app.use(express.json());
app.use(express.static(path.join(__dirname, 'views')));

// Health endpoint for Docker HEALTHCHECK
app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.post('/submit', async (req, res) => {
  try {
    const response = await axios.post(`${API_URL}/jobs`);
    res.json(response.data);
  } catch (err) {
    // Fix: propagate upstream status code when available
    const status = err.response ? err.response.status : 500;
    res.status(500).json({ error: "something went wrong" });
  }
});

app.get('/status/:id', async (req, res) => {
  try {
    const response = await axios.get(`${API_URL}/jobs/${req.params.id}`);
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: "something went wrong" });
  }
});

app.listen(3000, () => {
  console.log('Frontend running on port 3000');
});
