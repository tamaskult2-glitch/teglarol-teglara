export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { text, category } = req.body;

  if (!text || !category) {
    return res.status(400).json({ error: 'Missing text or category' });
  }

  try {
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'gpt-4-turbo',
        messages: [
          {
            role: 'system',
            content: `Te egy politikai ígéret-elemző rendszer vagy. Analizálj magyar nyelvű ígéreteket és javaslatokat.
            Mindig magyar nyelven válaszolj! Válaszod legyen JSON formátumban.`
          },
          {
            role: 'user',
            content: `Analizáld ezt az ígéretet/javaslatot:

"${text}"

Kategória: ${category}

Válaszolj PONTOSAN ezzel a JSON formátummal (semmi más):
{
  "sentiment": "pozitív|negatív|semleges",
  "confidence": 0-100,
  "status": "teljesült|teljesülés alatt|nem teljesült|feltételhez kötött",
  "reasoning": "1-2 mondatos magyarázat",
  "summary": "1-2 mondatos összefoglalás max 150 karakter"
}`
          }
        ],
        temperature: 0.7,
        max_tokens: 400
      })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error?.message || 'OpenAI API error');
    }

    const content = data.choices[0].message.content;

    // Parse JSON response
    try {
      const analysis = JSON.parse(content);
      return res.status(200).json(analysis);
    } catch (parseError) {
      // Fallback ha az OpenAI nem tiszta JSON-t ad vissza
      return res.status(200).json({
        sentiment: 'semleges',
        confidence: 50,
        status: 'teljesülés alatt',
        reasoning: content.substring(0, 200),
        summary: content.substring(0, 150)
      });
    }

  } catch (error) {
    console.error('API Error:', error);
    return res.status(500).json({
      error: error.message || 'Failed to analyze promise',
      sentiment: 'semleges',
      confidence: 0,
      status: 'ismeretlen'
    });
  }
}
