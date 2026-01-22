import React, { useState, createContext, useContext, useEffect, useRef } from 'react';
import { Upload, FileText, Download, AlertCircle, CheckCircle, Loader2, Lock } from 'lucide-react';

// ==================== TYPES & INTERFACES ====================

interface ExcelPreviewData {
  sheets: SheetData[];
  fileName: string;
}

interface SheetData {
  id: string;
  name: string;
  headers: string[];
  rows: string[][];
  totalRows: number;
}

interface ExtractionResult {
  bill_rate: string | null;
  duration: string | null;
  experience_required: string | null;
  gbams_rgs_id: string | null;
  ai_location: string | null;
  skills: string[] | null;
  role_description: string | null;
  msp_owner: string | null;
  ai_model_used?: string;
  ai_extraction_status?: string;
  ai_extraction_timestamp?: string;
}

interface ExcelExtractionResponse {
  results: Array<{
    row_index: number;
    original_jd: string;
    extracted_data: ExtractionResult;
  }>;
  request_id: string;
  total_processed: number;
  success_count?: number;
  failure_count?: number;
}

interface JDColumnSelection {
  sheetId: string | null;
  sheetName: string | null;
  columnIndex: number | null;
  columnHeader: string | null;
}

interface ProgressData {
  request_id: string;
  total: number;
  processed: number;
  complete: boolean;
}

// ==================== SELECTION CONTEXT (GLOBAL STATE) ====================

interface SelectionContextType {
  selection: JDColumnSelection;
  setSelection: (selection: JDColumnSelection) => void;
  clearSelection: () => void;
  isSheetLocked: (sheetId: string) => boolean;
  canSelectColumn: (sheetId: string) => boolean;
}

const SelectionContext = createContext<SelectionContextType | undefined>(undefined);

const SelectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selection, setSelectionState] = useState<JDColumnSelection>({
    sheetId: null,
    sheetName: null,
    columnIndex: null,
    columnHeader: null,
  });

  const setSelection = (newSelection: JDColumnSelection) => {
    setSelectionState(newSelection);
  };

  const clearSelection = () => {
    setSelectionState({
      sheetId: null,
      sheetName: null,
      columnIndex: null,
      columnHeader: null,
    });
  };

  const isSheetLocked = (sheetId: string): boolean => {
    return selection.sheetId !== null && selection.sheetId !== sheetId;
  };

  const canSelectColumn = (sheetId: string): boolean => {
    return selection.sheetId === null || selection.sheetId === sheetId;
  };

  return (
    <SelectionContext.Provider
      value={{ selection, setSelection, clearSelection, isSheetLocked, canSelectColumn }}
    >
      {children}
    </SelectionContext.Provider>
  );
};

const useSelection = () => {
  const context = useContext(SelectionContext);
  if (!context) {
    throw new Error('useSelection must be used within SelectionProvider');
  }
  return context;
};

// ==================== API SERVICE ====================

class JDParserAPI {
  private baseURL = 'http://localhost:8000/api/v1';

  async uploadExcel(file: File): Promise<ExcelPreviewData> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${this.baseURL}/excel/upload`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Upload failed');
    }
    
    return response.json();
  }

  async extractFromExcel(
    file: File,
    sheetId: string,
    sheetName: string,
    columnIndex: number
  ): Promise<{ request_id: string; status: string; message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('sheet_id', sheetId);
    formData.append('sheet_name', sheetName);
    formData.append('jd_column_index', columnIndex.toString());
    
    const response = await fetch(`${this.baseURL}/excel/extract`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Extraction failed');
    }
    
    return response.json();
  }

  async getExtractionStatus(requestId: string): Promise<any> {
    const response = await fetch(`${this.baseURL}/excel/status/${requestId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch status');
    }
    return response.json();
  }

  async getProgress(requestId: string): Promise<ProgressData> {
    const response = await fetch(`${this.baseURL}/progress/${requestId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch progress');
    }
    return response.json();
  }

  async extractFromText(jdText: string): Promise<ExtractionResult> {
    const response = await fetch(`${this.baseURL}/text/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jd_text: jdText }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Extraction failed');
    }
    
    return response.json();
  }

  async downloadExcel(requestId: string): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/excel/download/${requestId}`);
    if (!response.ok) throw new Error('Download failed');
    return response.blob();
  }
}

const api = new JDParserAPI();

// ==================== PROGRESS BAR COMPONENT ====================

const ProgressBar: React.FC<{
  total: number;
  processed: number;
}> = ({ total, processed }) => {
  const percentage = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
  
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-blue-900">
          Processing {processed} / {total} records
        </span>
        <span className="text-sm font-bold text-blue-900">{percentage}%</span>
      </div>
      <div className="w-full bg-blue-100 rounded-full h-3 overflow-hidden">
        <div
          className="bg-blue-600 h-full transition-all duration-300 ease-out rounded-full"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};

// ==================== EXCEL PREVIEW COMPONENT ====================

const ExcelPreview: React.FC<{
  previewData: ExcelPreviewData;
  selectedSheet: string;
  onSheetChange: (sheetId: string) => void;
  extractionResults: ExcelExtractionResponse | null;
}> = ({ previewData, selectedSheet, onSheetChange, extractionResults }) => {
  const { selection, setSelection, canSelectColumn, isSheetLocked } = useSelection();
  
  const currentSheet = previewData.sheets.find(s => s.id === selectedSheet);
  if (!currentSheet) return null;

  const isCurrentSheetLocked = isSheetLocked(currentSheet.id);
  const canInteract = canSelectColumn(currentSheet.id);

  const handleColumnClick = (columnIndex: number, columnHeader: string) => {
    if (!canInteract) return;

    if (selection.columnIndex === columnIndex && selection.sheetId === currentSheet.id) {
      setSelection({
        sheetId: null,
        sheetName: null,
        columnIndex: null,
        columnHeader: null,
      });
    } else {
      setSelection({
        sheetId: currentSheet.id,
        sheetName: currentSheet.name,
        columnIndex: columnIndex,
        columnHeader: columnHeader,
      });
    }
  };

  const getDisplayHeaders = () => {
    if (!extractionResults || selection.columnIndex === null || selection.sheetId !== currentSheet.id) {
      return currentSheet.headers;
    }

    const headers = [...currentSheet.headers];
    const extractedHeaders = [
      'Bill Rate',
      'Duration',
      'Experience',
      'GBAMS/RGS ID',
      'Location',
      'Skills',
      'Role Description',
      'MSP Owner'
    ];
    
    headers.splice(selection.columnIndex + 1, 0, ...extractedHeaders);
    return headers;
  };

  const getDisplayRow = (rowIndex: number) => {
    const row = currentSheet.rows[rowIndex];
    if (!extractionResults || selection.columnIndex === null || selection.sheetId !== currentSheet.id) {
      return row;
    }

    const result = extractionResults.results.find(r => r.row_index === rowIndex);
    if (!result) return row;

    const newRow = [...row];
    const extracted = result.extracted_data;
    const extractedValues = [
      extracted.bill_rate || '',
      extracted.duration || '',
      extracted.experience_required || '',
      extracted.gbams_rgs_id || '',
      extracted.ai_location || '',
      extracted.skills?.join(', ') || '',
      extracted.role_description || '',
      extracted.msp_owner || ''
    ];
    
    newRow.splice(selection.columnIndex + 1, 0, ...extractedValues);
    return newRow;
  };

  const displayHeaders = getDisplayHeaders();
  const isColumnSelected = (idx: number) => 
    selection.columnIndex === idx && selection.sheetId === currentSheet.id;
  const isExtractedColumn = (idx: number) => 
    extractionResults && 
    selection.sheetId === currentSheet.id &&
    selection.columnIndex !== null &&
    idx > selection.columnIndex && 
    idx <= selection.columnIndex + 8;

  return (
    <div className="border rounded-lg overflow-hidden bg-white">
      {previewData.sheets.length > 1 && (
        <div className="border-b bg-gray-50 flex gap-1 p-1">
          {previewData.sheets.map(sheet => {
            const sheetLocked = isSheetLocked(sheet.id);
            const isActive = selectedSheet === sheet.id;
            const isSelectedSheet = selection.sheetId === sheet.id;
            
            return (
              <button
                key={sheet.id}
                onClick={() => onSheetChange(sheet.id)}
                disabled={sheetLocked}
                title={sheetLocked ? `JD column already selected in "${selection.sheetName}"` : ''}
                className={`px-4 py-2 text-sm rounded flex items-center gap-2 transition-all ${
                  isActive
                    ? 'bg-white border border-gray-300 font-medium'
                    : sheetLocked
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed opacity-50'
                    : 'hover:bg-gray-100'
                } ${isSelectedSheet ? 'ring-2 ring-blue-400' : ''}`}
              >
                {sheet.name}
                {isSelectedSheet && <Lock className="h-3 w-3 text-blue-600" />}
              </button>
            );
          })}
        </div>
      )}
      
      {isCurrentSheetLocked && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-3 flex items-start">
          <Lock className="h-5 w-5 text-amber-600 mt-0.5 mr-2" />
          <div>
            <p className="text-sm font-medium text-amber-800">Sheet Locked (View Only)</p>
            <p className="text-sm text-amber-700 mt-1">
              JD column already selected in sheet "{selection.sheetName}". 
              Deselect the column to unlock other sheets.
            </p>
          </div>
        </div>
      )}
      
      <div className="overflow-auto max-h-96">
        <table className="w-full border-collapse">
          <thead className="bg-gray-100 sticky top-0">
            <tr>
              {displayHeaders.map((header, idx) => {
                const isOriginalColumn = !extractionResults || 
                  selection.sheetId !== currentSheet.id ||
                  selection.columnIndex === null ||
                  idx <= selection.columnIndex || 
                  idx > selection.columnIndex + 8;
                const isJDColumn = isColumnSelected(idx);
                const isExtracted = isExtractedColumn(idx);
                const canClick = isOriginalColumn && !extractionResults && canInteract;
                
                return (
                  <th
                    key={idx}
                    onClick={() => canClick && handleColumnClick(idx, header)}
                    className={`border border-gray-300 px-3 py-2 text-left text-sm font-semibold ${
                      isJDColumn
                        ? 'bg-blue-100 cursor-pointer hover:bg-blue-200'
                        : isExtracted
                        ? 'bg-green-50'
                        : canClick
                        ? 'cursor-pointer hover:bg-gray-200'
                        : isCurrentSheetLocked
                        ? 'cursor-not-allowed opacity-50'
                        : ''
                    } ${selection.sheetId && selection.sheetId !== currentSheet.id && isOriginalColumn && !extractionResults ? 'opacity-30' : ''}`}
                  >
                    {header}
                    {isJDColumn && <span className="ml-2 text-blue-600">📋 JD</span>}
                    {isExtracted && <span className="ml-2 text-green-600">✨ AI</span>}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {currentSheet.rows.slice(0, 50).map((_, rowIdx) => {
              const displayRow = getDisplayRow(rowIdx);
              return (
                <tr key={rowIdx} className="hover:bg-gray-50">
                  {displayRow.map((cell, cellIdx) => (
                    <td
                      key={cellIdx}
                      className="border border-gray-300 px-3 py-2 text-sm"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      
      <div className="bg-gray-50 px-4 py-2 text-sm text-gray-600 border-t">
        Showing 50 of {currentSheet.totalRows} rows
      </div>
    </div>
  );
};

// ==================== EXCEL MODE COMPONENT ====================

const ExcelMode: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<ExcelPreviewData | null>(null);
  const [selectedSheet, setSelectedSheet] = useState<string>('');
  const [extractionResults, setExtractionResults] = useState<ExcelExtractionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  
  // Progress tracking state
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [currentRequestId, setCurrentRequestId] = useState<string | null>(null);
  const pollingIntervalRef = useRef<number | null>(null);

  const { selection, clearSelection } = useSelection();

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  // Poll progress when extracting
  useEffect(() => {
    if (extracting && currentRequestId) {
      // Start polling
      pollingIntervalRef.current = setInterval(async () => {
        try {
          const progressData = await api.getProgress(currentRequestId);
          setProgress(progressData);
          
          // Stop polling when complete
          if (progressData.complete) {
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
          }
        } catch (err) {
          // Progress endpoint might not be ready yet, continue polling
          console.log('Waiting for progress data...');
        }
      }, 500); // Poll every 500ms

      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }
  }, [extracting, currentRequestId]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const uploadedFile = e.target.files?.[0];
    if (!uploadedFile) return;

    setFile(uploadedFile);
    setLoading(true);
    setError(null);
    setPreviewData(null);
    setExtractionResults(null);
    setProgress(null);
    setCurrentRequestId(null);
    clearSelection();

    try {
      const data = await api.uploadExcel(uploadedFile);
      setPreviewData(data);
      setSelectedSheet(data.sheets[0].id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleExtract = async () => {
    if (!file || !selection.sheetId || !selection.sheetName || selection.columnIndex === null) {
      setError('Invalid selection state. Please select a JD column.');
      return;
    }

    setExtracting(true);
    setError(null);
    setProgress(null);
    setExtractionResults(null);

    try {
      // Start extraction - get request_id immediately
      const startResponse = await api.extractFromExcel(
        file,
        selection.sheetId,
        selection.sheetName,
        selection.columnIndex
      );
      
      // Set request ID for polling
      setCurrentRequestId(startResponse.request_id);
      
      // Wait for completion by polling progress
      await waitForCompletion(startResponse.request_id);
      
    } catch (err) {
      setError((err as Error).message);
      setExtracting(false);
    }
  };

  const waitForCompletion = async (requestId: string) => {
    // Poll until complete
    let attempts = 0;
    const maxAttempts = 300; // 5 minutes max (300 seconds)
    
    while (attempts < maxAttempts) {
      try {
        const status = await api.getExtractionStatus(requestId);
        
        console.log('Status check:', status);
        
        if (status.status === 'complete') {
          // Build ExcelExtractionResponse from status
          const results: ExcelExtractionResponse = {
            request_id: requestId,
            results: status.results || [],
            total_processed: status.total_processed || 0,
            success_count: status.success_count,
            failure_count: status.failure_count
          };
          
          // CRITICAL FIX: Set progress to 100% when complete
          if (progress) {
            setProgress({
              request_id: requestId,
              total: progress.total,
              processed: progress.total, // Force 100%
              complete: true
            });
          }
          
          setExtractionResults(results);
          setExtracting(false);
          console.log('Extraction complete!', results);
          break;
        }
        
        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
      } catch (err) {
        console.error('Status check error:', err);
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
      }
    }
    
    if (attempts >= maxAttempts) {
      setError('Extraction timed out. Please check the status manually.');
      setExtracting(false);
    }
  };

  const handleDownloadExcel = async () => {
    if (!extractionResults) return;
    try {
      const blob = await api.downloadExcel(extractionResults.request_id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `jd_extraction_${extractionResults.request_id}.xlsx`;
      a.click();
    } catch (err) {
      setError('Download failed');
    }
  };

  const handleDownloadJSON = () => {
    if (!extractionResults) return;
    const blob = new Blob([JSON.stringify(extractionResults, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jd_extraction_${extractionResults.request_id}.json`;
    a.click();
  };

  return (
    <div className="space-y-6">
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors">
        <input
          type="file"
          accept=".xlsx,.xls"
          onChange={handleFileUpload}
          className="hidden"
          id="excel-upload"
        />
        <label htmlFor="excel-upload" className="cursor-pointer">
          <Upload className="mx-auto h-12 w-12 text-gray-400" />
          <p className="mt-2 text-sm text-gray-600">
            Click to upload Excel file (.xlsx, .xls)
          </p>
          {file && <p className="mt-2 text-sm font-medium text-blue-600">{file.name}</p>}
        </label>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <span className="ml-3 text-gray-600">Processing Excel file...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
          <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
          <div className="ml-3">
            <p className="text-sm font-medium text-red-800">Error</p>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Progress Bar - Show during extraction OR when complete */}
      {(extracting || extractionResults) && progress && (
        <ProgressBar total={progress.total} processed={progress.processed} />
      )}

      {previewData && (
        <>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-blue-800">
              <strong>Step 1:</strong> Click on the column header that contains Job Descriptions
            </p>
            {selection.columnIndex !== null && (
              <p className="text-sm text-blue-800 mt-2">
                <CheckCircle className="inline h-4 w-4 mr-1" />
                Selected: Sheet "{selection.sheetName}" → Column "{selection.columnHeader}" (Index {selection.columnIndex})
              </p>
            )}
          </div>

          <ExcelPreview
            previewData={previewData}
            selectedSheet={selectedSheet}
            onSheetChange={setSelectedSheet}
            extractionResults={extractionResults}
          />

          <div className="flex gap-3">
            <button
              onClick={handleExtract}
              disabled={selection.columnIndex === null || extracting}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center"
            >
              {extracting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Extracting...
                </>
              ) : (
                'Extract JD Data'
              )}
            </button>

            {extractionResults && (
              <>
                <button
                  onClick={handleDownloadExcel}
                  className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download Excel
                </button>
                <button
                  onClick={handleDownloadJSON}
                  className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download JSON
                </button>
              </>
            )}
          </div>

          {extractionResults && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <CheckCircle className="inline h-5 w-5 text-green-600 mr-2" />
              <span className="text-sm font-medium text-green-800">
                Successfully extracted {extractionResults.total_processed} job descriptions from sheet "{selection.sheetName}"
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ==================== TEXT MODE COMPONENT ====================

const TextMode: React.FC = () => {
  const [jdText, setJdText] = useState('');
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExtract = async () => {
    if (!jdText.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await api.extractFromText(jdText);
      setResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadJSON = (includeOriginal: boolean) => {
    if (!result) return;
    const data = includeOriginal ? { original_jd: jdText, extracted_data: result } : result;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jd_extraction_${Date.now()}.json`;
    a.click();
  };

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Paste Job Description Text
        </label>
        <textarea
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          placeholder="Paste the complete job description here..."
          className="w-full h-64 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
        />
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
          <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
          <div className="ml-3">
            <p className="text-sm font-medium text-red-800">Error</p>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      )}

      <button
        onClick={handleExtract}
        disabled={!jdText.trim() || loading}
        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center"
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Extracting...
          </>
        ) : (
          'Extract JD Data'
        )}
      </button>

      {result && (
        <>
          <div className="bg-white border rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-4 py-3 border-b">
              <h3 className="text-lg font-semibold">Extraction Results</h3>
            </div>
            <div className="overflow-auto">
              <table className="w-full">
                <tbody className="divide-y">
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-700">Bill Rate</td>
                    <td className="px-4 py-3">{result.bill_rate || 'N/A'}</td>
                  </tr>
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-700">Duration</td>
                    <td className="px-4 py-3">{result.duration || 'N/A'}</td>
                  </tr>
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-700">Experience Required</td>
                    <td className="px-4 py-3">{result.experience_required || 'N/A'}</td>
                  </tr>
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-700">GBAMS/RGS ID</td>
                    <td className="px-4 py-3">{result.gbams_rgs_id || 'N/A'}</td>
                  </tr>
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-700">Location</td>
                    <td className="px-4 py-3">{result.ai_location || 'N/A'}</td>
                  </tr>
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-700">Skills</td>
                    <td className="px-4 py-3">{result.skills?.join(', ') || 'N/A'}</td>
                  </tr>
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-700">Role Description</td>
                    <td className="px-4 py-3">{result.role_description || 'N/A'}</td>
                  </tr>
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-700">MSP Owner</td>
                    <td className="px-4 py-3">{result.msp_owner || 'N/A'}</td>
                  </tr>
                  {result.ai_model_used && (
                    <tr className="bg-blue-50">
                      <td className="px-4 py-3 font-medium text-blue-700">AI Model Used</td>
                      <td className="px-4 py-3 text-blue-900">{result.ai_model_used}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => handleDownloadJSON(false)}
              className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center"
            >
              <Download className="h-4 w-4 mr-2" />
              Download JSON (Extracted Only)
            </button>
            <button
              onClick={() => handleDownloadJSON(true)}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center"
            >
              <Download className="h-4 w-4 mr-2" />
              Download JSON (With Original)
            </button>
          </div>
        </>
      )}
    </div>
  );
};

// ==================== MAIN APP COMPONENT ====================

const JDParserApp: React.FC = () => {
  const [mode, setMode] = useState<'excel' | 'text'>('excel');

  return (
    <SelectionProvider>
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">JD Parser</h1>
            <p className="text-gray-600">
              Enterprise-grade job description extraction powered by AI
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-sm border p-6">
            <div className="flex gap-3 mb-6 border-b pb-4">
              <button
                onClick={() => setMode('excel')}
                className={`px-6 py-2 rounded-lg font-medium flex items-center ${
                  mode === 'excel'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <Upload className="h-4 w-4 mr-2" />
                Excel Mode
              </button>
              <button
                onClick={() => setMode('text')}
                className={`px-6 py-2 rounded-lg font-medium flex items-center ${
                  mode === 'text'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <FileText className="h-4 w-4 mr-2" />
                Text Mode
              </button>
            </div>

            {mode === 'excel' ? <ExcelMode /> : <TextMode />}
          </div>
        </div>
      </div>
    </SelectionProvider>
  );
};

export default JDParserApp;