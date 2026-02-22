"use client";

import { AIInputWithFile } from "@/components/ui/ai-input-with-file";
import Link from "next/link";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Eye,
  Cpu,
  FileSearch,
  ChevronDown,
  FileImage,
  Activity,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const ANALYZE_ENDPOINT = "/api/run-analyze";

interface Signal {
  layer: string;
  name: string;
  value: string;
  flag?: string;
  weight?: number;
  confidence?: number;
  models_used?: string[];
  models_failed?: string[];
  all_failed?: boolean;
}

interface AnalyzeResult {
  file_name: string;
  type: string;
  risk_score: number;
  classification: "low_risk" | "medium_risk" | "high_risk";
  confidence: number | null;
  recommendation: string;
  signals: Signal[];
  layer_scores: Record<string, number>;
  models_used: string[];
  models_failed: string[];
  processing_time_ms: number;
}

function RiskGauge({ score, classification }: { score: number; classification: string }) {
  const angle = (score / 100) * 180 - 90;
  const color =
    classification === "low_risk"
      ? "#34d399"
      : classification === "medium_risk"
        ? "#fbbf24"
        : "#f87171";
  const bgTrack =
    classification === "low_risk"
      ? "rgba(52,211,153,0.15)"
      : classification === "medium_risk"
        ? "rgba(251,191,36,0.15)"
        : "rgba(248,113,113,0.15)";

  return (
    <div className="relative w-52 h-28 mx-auto">
      <svg viewBox="0 0 200 110" className="w-full h-full">
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="16"
          strokeLinecap="round"
        />
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={bgTrack}
          strokeWidth="16"
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * 251.2} 251.2`}
        />
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * 251.2} 251.2`}
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
        <line
          x1="100"
          y1="100"
          x2="100"
          y2="35"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
          transform={`rotate(${angle}, 100, 100)`}
          style={{ filter: `drop-shadow(0 0 4px ${color})` }}
        />
        <circle cx="100" cy="100" r="5" fill={color} />
      </svg>
    </div>
  );
}

function LayerBar({ name, score }: { name: string; score: number }) {
  const label =
    name === "metadata"
      ? "Metadata"
      : name === "forensics"
        ? "Forensics"
        : name === "ai_detection"
          ? "AI Detection"
          : name;

  const icon =
    name === "metadata" ? (
      <FileSearch className="w-3.5 h-3.5 text-white/50" />
    ) : name === "forensics" ? (
      <Eye className="w-3.5 h-3.5 text-white/50" />
    ) : (
      <Cpu className="w-3.5 h-3.5 text-white/50" />
    );

  const barColor =
    score <= 30
      ? "bg-emerald-400"
      : score <= 65
        ? "bg-amber-400"
        : "bg-red-400";

  const textColor =
    score <= 30
      ? "text-emerald-400"
      : score <= 65
        ? "text-amber-400"
        : "text-red-400";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-white/70 text-xs font-medium">{label}</span>
        </div>
        <span className={cn("text-xs font-bold tabular-nums", textColor)}>
          {score}
        </span>
      </div>
      <div className="h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-700", barColor)}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

function SignalCard({ signal }: { signal: Signal }) {
  const flagColor =
    signal.flag === "suspicious"
      ? "border-red-500/30 bg-red-500/5"
      : signal.flag === "clean"
        ? "border-emerald-500/30 bg-emerald-500/5"
        : "border-white/10 bg-white/[0.02]";

  const flagDot =
    signal.flag === "suspicious"
      ? "bg-red-400"
      : signal.flag === "clean"
        ? "bg-emerald-400"
        : "bg-white/30";

  const flagLabel =
    signal.flag === "suspicious"
      ? "Suspicious"
      : signal.flag === "clean"
        ? "Clean"
        : "Neutral";

  const flagTextColor =
    signal.flag === "suspicious"
      ? "text-red-400/70"
      : signal.flag === "clean"
        ? "text-emerald-400/70"
        : "text-white/30";

  const layerIcon =
    signal.layer === "metadata" ? (
      <FileSearch className="w-3.5 h-3.5" />
    ) : signal.layer === "forensics" ? (
      <Eye className="w-3.5 h-3.5" />
    ) : (
      <Cpu className="w-3.5 h-3.5" />
    );

  return (
    <div className={cn("p-4 rounded-xl border transition-colors", flagColor)}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 mb-1.5">
          <span className={cn("w-2 h-2 rounded-full flex-shrink-0", flagDot)} />
          <span className="text-white/40">{layerIcon}</span>
          <span className="text-white/90 font-medium text-sm">{signal.name}</span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {signal.weight !== undefined && signal.weight !== 0 && (
            <span
              className={cn(
                "text-[10px] font-mono px-1.5 py-0.5 rounded",
                signal.weight > 0
                  ? "bg-red-500/10 text-red-400/80"
                  : "bg-emerald-500/10 text-emerald-400/80"
              )}
            >
              {signal.weight > 0 ? "+" : ""}
              {signal.weight}
            </span>
          )}
          <span className={cn("text-[10px] uppercase tracking-wider font-medium", flagTextColor)}>
            {flagLabel}
          </span>
        </div>
      </div>
      <p className="text-white/60 text-sm leading-relaxed pl-4 mt-1">{signal.value}</p>
      {signal.confidence !== undefined && (
        <div className="pl-4 mt-2 flex items-center gap-2">
          <div className="h-1 w-16 bg-white/[0.06] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-white/30"
              style={{ width: `${Math.round(signal.confidence * 100)}%` }}
            />
          </div>
          <span className="text-white/30 text-[10px]">
            {Math.round(signal.confidence * 100)}% confidence
          </span>
        </div>
      )}
    </div>
  );
}

export default function AnalyzePage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSignals, setShowSignals] = useState(false);

  const handleSubmit = async (_message: string, file?: File) => {
    if (!file) {
      setError("Please upload an image to analyze.");
      return;
    }

    setError(null);
    setResult(null);
    setShowSignals(false);
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

  const getClassificationConfig = (classification: string) => {
    switch (classification) {
      case "low_risk":
        return {
          color: "text-emerald-400",
          bg: "bg-emerald-400/10",
          border: "border-emerald-400/20",
          label: "Low Risk",
          icon: <ShieldCheck className="w-6 h-6 text-emerald-400" />,
          desc: "Likely authentic",
        };
      case "medium_risk":
        return {
          color: "text-amber-400",
          bg: "bg-amber-400/10",
          border: "border-amber-400/20",
          label: "Medium Risk",
          icon: <ShieldAlert className="w-6 h-6 text-amber-400" />,
          desc: "Mixed signals detected",
        };
      case "high_risk":
        return {
          color: "text-red-400",
          bg: "bg-red-400/10",
          border: "border-red-400/20",
          label: "High Risk",
          icon: <ShieldX className="w-6 h-6 text-red-400" />,
          desc: "Likely AI-generated",
        };
      default:
        return {
          color: "text-white/70",
          bg: "bg-white/5",
          border: "border-white/10",
          label: classification,
          icon: <Shield className="w-6 h-6 text-white/70" />,
          desc: "",
        };
    }
  };

  const groupedSignals = result
    ? {
        metadata: result.signals.filter((s) => s.layer === "metadata"),
        forensics: result.signals.filter((s) => s.layer === "forensics"),
        ai_detection: result.signals.filter((s) => s.layer === "ai_detection"),
      }
    : null;

  return (
    <main className="min-h-screen w-full bg-black flex flex-col">
      <nav className="p-5">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-white/50 hover:text-white text-sm transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
      </nav>

      <div className="flex-1 flex flex-col items-center px-4 pb-12 pt-8 md:pt-16">
        <h1
          className="text-4xl md:text-6xl tracking-tight mb-3 text-white text-center"
          style={{ fontFamily: "var(--font-instrument-serif)" }}
        >
          Seeing is no longer believing
        </h1>
        <p className="text-white/50 text-sm md:text-base mb-10 text-center max-w-lg">
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

        {/* Loading */}
        {loading && (
          <div className="flex flex-col items-center gap-3 mt-12 animate-in fade-in duration-300">
            <div className="relative">
              <div className="w-16 h-16 rounded-full border-2 border-white/10 flex items-center justify-center">
                <Loader2 className="w-7 h-7 text-white/80 animate-spin" />
              </div>
              <div className="absolute inset-0 rounded-full border-2 border-t-white/40 animate-spin" style={{ animationDuration: "1.5s" }} />
            </div>
            <p className="text-white/60 text-sm">Analyzing image...</p>
            <p className="text-white/30 text-xs">Running metadata, forensics &amp; AI detection</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-start gap-3 mt-8 p-5 rounded-2xl bg-red-500/[0.07] border border-red-500/20 max-w-xl w-full animate-in fade-in slide-in-from-bottom-2 duration-300">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-red-400 font-semibold text-sm">Analysis Failed</p>
              <p className="text-red-300/80 text-sm mt-1 leading-relaxed">{error}</p>
            </div>
          </div>
        )}

        {/* Results */}
        {result && !loading && (
          <div className="mt-10 w-full max-w-xl space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* File info */}
            <div className="flex items-center gap-2 px-1">
              <FileImage className="w-4 h-4 text-white/30" />
              <span className="text-white/40 text-xs truncate">{result.file_name}</span>
              <span className="text-white/20 text-xs">·</span>
              <span className="text-white/30 text-xs">{(result.processing_time_ms / 1000).toFixed(1)}s</span>
            </div>

            {/* Main result card */}
            {(() => {
              const config = getClassificationConfig(result.classification);
              return (
                <div className={cn(
                  "p-8 rounded-2xl border backdrop-blur-sm",
                  config.border,
                  config.bg
                )}>
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                      {config.icon}
                      <div>
                        <p className={cn("text-lg font-bold", config.color)}>
                          {config.label}
                        </p>
                        <p className="text-white/40 text-xs">{config.desc}</p>
                      </div>
                    </div>
                    <p className="text-white/30 text-[10px] uppercase tracking-widest">
                      Risk Score
                    </p>
                  </div>

                  <RiskGauge score={result.risk_score} classification={result.classification} />
                  <p className="text-center mt-1">
                    <span className={cn("text-5xl font-bold tabular-nums", config.color)}>
                      {result.risk_score}
                    </span>
                    <span className="text-white/30 text-lg ml-1">/ 100</span>
                  </p>

                  {result.confidence !== null && (
                    <div className="mt-6 flex items-center justify-center gap-2">
                      <div className="h-1.5 w-32 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-1000"
                          style={{
                            width: `${Math.round(result.confidence * 100)}%`,
                            backgroundColor:
                              result.classification === "low_risk"
                                ? "#34d399"
                                : result.classification === "medium_risk"
                                  ? "#fbbf24"
                                  : "#f87171",
                          }}
                        />
                      </div>
                      <span className="text-white/50 text-xs">
                        {Math.round(result.confidence * 100)}% AI confidence
                      </span>
                    </div>
                  )}

                  <p className="text-white/70 text-sm mt-6 text-center leading-relaxed">
                    {result.recommendation}
                  </p>
                </div>
              );
            })()}

            {/* Layer breakdown */}
            {result.layer_scores && Object.keys(result.layer_scores).length > 0 && (
              <div className="p-5 rounded-2xl border border-white/10 bg-white/[0.02]">
                <div className="flex items-center gap-2 mb-4">
                  <Activity className="w-4 h-4 text-white/50" />
                  <span className="text-white/70 text-sm font-semibold">Layer Breakdown</span>
                </div>
                <div className="space-y-3">
                  {Object.entries(result.layer_scores).map(([layer, score]) => (
                    <LayerBar key={layer} name={layer} score={score} />
                  ))}
                </div>
              </div>
            )}

            {/* Models used/failed */}
            {(result.models_used.length > 0 || result.models_failed.length > 0) && (
              <div className="p-5 rounded-2xl border border-white/10 bg-white/[0.02]">
                <div className="flex items-center gap-2 mb-3">
                  <Cpu className="w-4 h-4 text-white/50" />
                  <span className="text-white/70 text-sm font-semibold">AI Models</span>
                </div>
                <div className="space-y-1.5">
                  {result.models_used.map((model) => (
                    <div key={model} className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400/70" />
                      <span className="text-white/60 text-xs">{model}</span>
                    </div>
                  ))}
                  {result.models_failed.map((model) => (
                    <div key={model} className="flex items-center gap-2">
                      <XCircle className="w-3.5 h-3.5 text-red-400/70" />
                      <span className="text-white/40 text-xs">{model}</span>
                      <span className="text-white/20 text-[10px]">failed</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Signal details (grouped by layer) */}
            {result.signals && result.signals.length > 0 && groupedSignals && (
              <div>
                <button
                  onClick={() => setShowSignals(!showSignals)}
                  className="w-full flex items-center justify-between px-5 py-3.5 rounded-xl bg-white/[0.03] border border-white/10 hover:bg-white/[0.06] transition-colors cursor-pointer"
                >
                  <span className="text-white/70 text-sm font-medium">
                    All Signals ({result.signals.length})
                  </span>
                  <ChevronDown
                    className={cn(
                      "w-4 h-4 text-white/40 transition-transform duration-300",
                      showSignals && "rotate-180"
                    )}
                  />
                </button>

                {showSignals && (
                  <div className="mt-3 space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    {(["metadata", "forensics", "ai_detection"] as const).map((layer) => {
                      const signals = groupedSignals[layer];
                      if (!signals || signals.length === 0) return null;
                      const layerLabel =
                        layer === "metadata"
                          ? "Metadata Analysis"
                          : layer === "forensics"
                            ? "Forensics Analysis"
                            : "AI Detection";
                      return (
                        <div key={layer}>
                          <p className="text-white/40 text-[10px] uppercase tracking-widest font-medium mb-2 px-1">
                            {layerLabel}
                          </p>
                          <div className="space-y-2">
                            {signals.map((signal, i) => (
                              <SignalCard key={i} signal={signal} />
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
