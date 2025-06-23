"use client";

import { useState, useRef } from "react";

export function AutoInsurance() {
  const [referralPdf, setReferralPdf] = useState<File | null>(null);
  const [paPdf, setPaPdf] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<string>("");
  const [resultPdfUrl, setResultPdfUrl] = useState<string | null>(null);
  const referralPdfUrl = useRef<string | null>(null);

  const handleSubmit = async () => {
    if (!referralPdf || !paPdf) return;
    setIsLoading(true);
    setResult("");
    setResultPdfUrl(null);
    try {
      const formData = new FormData();
      formData.append("referral_pdf", referralPdf);
      formData.append("pa_pdf", paPdf);

      const response = await fetch("http://127.0.0.1:8000/process_pdfs/", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error("Failed to process PDFs");

      // Always try to get the PDF if content-type is PDF
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/pdf")) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setResultPdfUrl(url);
        setResult("PDF generated. Preview below.");
        return; // Don't try to parse JSON if PDF
      }
      // Otherwise, try to parse JSON and look for PDF
      const data = await response.json();
      setResult(JSON.stringify(data, null, 2));
      if (data.result_pdf_url) {
        setResultPdfUrl(data.result_pdf_url);
      } else if (data.result_pdf_base64) {
        // If base64, convert to blob URL
        const byteCharacters = atob(data.result_pdf_base64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: "application/pdf" });
        const url = URL.createObjectURL(blob);
        setResultPdfUrl(url);
      }
    } catch (error: any) {
      setResult("Error: " + (error?.message || error));
    } finally {
      setIsLoading(false);
    }
  };

  // Create a URL for the uploaded referral PDF for preview
  if (referralPdf && !referralPdfUrl.current) {
    referralPdfUrl.current = URL.createObjectURL(referralPdf);
  }
  if (!referralPdf && referralPdfUrl.current) {
    URL.revokeObjectURL(referralPdfUrl.current);
    referralPdfUrl.current = null;
  }

  // A4 aspect ratio: 1:1.414 (e.g., width: 595px, height: 842px)
  // We'll use 100% width (max 595px) and height auto, or set height to 70vw * 1.414 for responsiveness
  const a4Width = 595;
  const a4Height = 842;

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#f8fafc] to-[#e2e8f0] flex flex-col items-center justify-center">
      <div className="space-y-6 max-w-xl w-full mx-auto mt-10 bg-white shadow-xl rounded-2xl p-8 border border-gray-200">
        <h1 className="text-3xl font-bold text-[#0a4d5a] mb-2 text-center">AutoInsurance</h1>
        <p className="text-gray-600 mb-6 text-center">Upload your <b>Referral Package</b> and <b>Prior Authorization</b> to process your insurance documents automatically.</p>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Referral Package (PDF)</label>
            <input
              type="file"
              accept="application/pdf"
              onChange={e => setReferralPdf(e.target.files?.[0] || null)}
              className="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg text-gray-700 file:text-gray-600 file:bg-transparent file:border-none focus:outline-none focus:ring-2 focus:ring-[#0a4d5a] focus:border-[#0a4d5a] transition-all"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Prior Authoruzation (PDF)</label>
            <input
              type="file"
              accept="application/pdf"
              onChange={e => setPaPdf(e.target.files?.[0] || null)}
              className="w-full px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg text-gray-700 file:text-gray-600 file:bg-transparent file:border-none focus:outline-none focus:ring-2 focus:ring-[#0a4d5a] focus:border-[#0a4d5a] transition-all"
            />
          </div>
          <button
            type="button"
            disabled={!referralPdf || !paPdf || isLoading}
            onClick={handleSubmit}
            className={
              `w-full px-6 py-3 rounded-lg font-semibold text-white transition-all duration-200
              ${isLoading ? 'bg-[#0a4d5a]/70 cursor-not-allowed' : 'bg-[#0a4d5a] hover:bg-[#128fa1] active:scale-95 shadow-md hover:shadow-lg'}
              focus:outline-none focus:ring-2 focus:ring-[#0a4d5a] focus:ring-offset-2 focus:ring-offset-white relative`
            }
          >
            {isLoading ? (
              <div className="flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                Processing...
              </div>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" /></svg>
                Process Documents
              </span>
            )}
          </button>
        </div>
        {result && (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h3 className="text-lg font-semibold text-[#0a4d5a] mb-2">Result</h3>
            <pre className="text-gray-700 whitespace-pre-wrap break-all text-sm">{result}</pre>
          </div>
        )}
      </div>
      {/* PDF Preview Section */}
      {(referralPdfUrl.current || resultPdfUrl) && (
        <div className="w-full max-w-5xl mt-10 flex flex-col items-center">
          <h2 className="text-2xl font-bold text-[#0a4d5a] mb-4">Documents Review</h2>
          <div className="flex flex-col md:flex-row gap-8 w-full">
            <div className="flex-1 bg-white rounded-lg shadow border border-gray-200 p-4">
              <h3 className="text-lg font-semibold text-[#0a4d5a] mb-2 text-center">Referral Package</h3>
              {referralPdfUrl.current ? (
                <iframe
                  src={referralPdfUrl.current}
                  title="Referral PDF"
                  className="w-full max-w-[595px] h-[842px] border rounded bg-gray-100 mx-auto"
                  frameBorder={0}
                  allowFullScreen
                />
              ) : (
                <div className="text-gray-400 text-center">No Referral PDF uploaded.</div>
              )}
            </div>
            <div className="flex-1 bg-white rounded-lg shadow border border-gray-200 p-4">
              <h3 className="text-lg font-semibold text-[#0a4d5a] mb-2 text-center">Prior Authorization (Filled)</h3>
              {resultPdfUrl ? (
                <iframe
                  src={resultPdfUrl}
                  title="Result PDF"
                  className="w-full max-w-[595px] h-[842px] border rounded bg-gray-100 mx-auto"
                  frameBorder={0}
                  allowFullScreen
                />
              ) : (
                <div className="text-gray-400 text-center">No Result PDF generated yet.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
