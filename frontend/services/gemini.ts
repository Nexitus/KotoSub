
import { GoogleGenAI } from "@google/genai";

export class GeminiService {
  private ai: GoogleGenAI;

  constructor(apiKey: string) {
    this.ai = new GoogleGenAI({ apiKey });
  }

  async translateSubtitles(text: string, sourceLang: string, targetLang: string) {
    try {
      const response = await this.ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: `Translate the following video subtitle text from ${sourceLang} to ${targetLang}. Maintain timestamp formatting if present:\n\n${text}`,
        config: {
          systemInstruction: "You are a professional video translator. Translate accurately while preserving colloquialisms and emotional nuance.",
          temperature: 0.3,
        }
      });
      return response.text;
    } catch (error) {
      console.error("Gemini Translation Error:", error);
      throw error;
    }
  }

  async analyzeVideoContent(description: string) {
    try {
      const response = await this.ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: `Analyze this video metadata and suggest the best tone for translations: ${description}`,
      });
      return response.text;
    } catch (error) {
      console.error("Gemini Analysis Error:", error);
      return "Maintain professional and clear tone.";
    }
  }
}
