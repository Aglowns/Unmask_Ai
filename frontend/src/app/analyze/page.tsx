"use client";

import { AIInputWithFile } from "@/components/ui/ai-input-with-file";
import Link from "next/link";
import { ArrowLeft, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { useState } from "react";

const ANALYZE_ENDPOINT = "/api/run-analyze";

interface AnalyzeResult {
  file_name: string;
  risk_score: number;
  classification: "low_risk" | "medium_risk" | "high_risk";
  confidence: number | null;
  recommendation: string;
  signals: Array<{
    layer: string;
    name: string;
    value: string;
    flag?: string;
  }>;
  processing_time_ms: number;
}

export default function AnalyzePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (message: string, file?: File) => {
    if (!file) {
      setError("Please upload an image to analyze.");
      return;
    }

    setError(null);
    setResult(null);
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(ANALYZE_ENDPOINT, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const message =
          typeof errData.detail === "string"
            ? errData.detail
            : errData.detail?.message || `Request failed: ${response.status} ${response.statusText}`;
        throw new Error(message);
      }

      const data: AnalyzeResult = await response.json();
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to analyze image. Is the backend running?"
      );
    } finally {
      setLoading(false);
    }
  };

  const getClassificationColor = (classification: string) => {
    switch (classification) {
      case "low_risk":
        return "text-emerald-400";
      case "medium_risk":
        return "text-amber-400";
      case "high_risk":
        return "text-red-400";
      default:
        return "text-white/70";
    }
  };

  const getClassificationLabel = (classification: string) => {
    switch (classification) {
      case "low_risk":
        return "Low Risk";
      case "medium_risk":
        return "Medium Risk";
      case "high_risk":
        return "High Risk";
      default:
        return classification;
    }
  };

  return (
    <main className="min-h-screen w-full bg-black flex flex-col">
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-8">
        <h1
          className="text-3xl md:text-5xl tracking-tight mb-2 text-white text-center"
          style={{ fontFamily: "var(--font-instrument-serif)" }}
        >
          Seeing is no longer believing
        </h1>
        <p className="text-white/70 text-sm md:text-base mb-8 text-center max-w-md">
          Upload an image to analyze whether it&apos;s real or AI-generated
        </p>

        <div className="w-full max-w-xl">
          <AIInputWithFile
            placeholder="Upload an image to analyze..."
            onSubmit={handleSubmit}
            accept="image/*"
            maxFileSize={10}
          />
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-white/70 mt-6">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Analyzing image...</span>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 mt-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20 max-w-xl w-full">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-red-400 font-medium">Error</p>
              <p className="text-red-300/90 text-sm mt-1">{error}</p>
            </div>
          </div>
        )}

        {result && !loading && (
          <div className="mt-8 w-full max-w-xl space-y-4">
            <div className="p-6 rounded-xl bg-white/5 border border-white/10">
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span className="text-white font-medium">Analysis complete</span>
              </div>

              <div className="flex items-baseline gap-3 mb-4">
                <span className="text-4xl font-bold text-white">
                  {result.risk_score}
                </span>
                <span className="text-white/50">/ 100 risk score</span>
              </div>

              <p
                className={`text-lg font-semibold ${getClassificationColor(result.classification)}`}
              >
                {getClassificationLabel(result.classification)}
              </p>

              {result.confidence !== null && (
                <p className="text-white/60 text-sm mt-1">
                  AI confidence: {Math.round(result.confidence * 100)}%
                </p>
              )}

              <p className="text-white/80 mt-4 text-sm">{result.recommendation}</p>

              {result.processing_time_ms > 0 && (
                <p className="text-white/40 text-xs mt-6">
                  Processed in {result.processing_time_ms}ms
                </p>
              )}
            </div>

            {result.signals && result.signals.length > 0 && (
              <details className="group">
                <summary className="cursor-pointer text-white/70 text-sm hover:text-white/90 transition-colors">
                  View signal details
                </summary>
                <div className="mt-3 space-y-2">
                  {result.signals.map((signal, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg bg-white/5 text-sm"
                    >
                      <span className="text-white/50">[{signal.layer}]</span>{" "}
                      <span className="text-white/90 font-medium">{signal.name}</span>
                      <p className="text-white/70 mt-1">{signal.value}</p>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </div>

      <div className="p-4">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-white/70 hover:text-white text-sm transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to home
        </Link>
      </div>
    </main>
  );
}
