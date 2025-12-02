export interface GFSPoint {
  lat: number;
  lon: number;
  tmp2m: number;
  press: number;
}

export interface ProcessingResult {
  allPoints: GFSPoint[];
  matches: GFSPoint[];
  timestamp: string;
}

export interface WorkerMessage {
  type: 'INIT' | 'RUN';
}

export interface WorkerResponse {
  type: 'STATUS' | 'RESULT' | 'ERROR';
  message?: string;
  data?: ProcessingResult;
}

export type PlotVariable = 'tmp2m' | 'press';
