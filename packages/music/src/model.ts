export type SourceSpan = { start: number; end: number };
export type Diagnostic = { code: string; severity: 'info'|'warning'|'error'; message: string; line?: number; page?: number };
export type Segment = { chord?: string; lyric: string; span: SourceSpan };
export type MusicBlock =
  | { kind: 'lyric'; segments: Segment[]; span: SourceSpan }
  | { kind: 'tab'; text: string; groups: {startLine: number; endLine: number}[]; label?: string; span: SourceSpan }
  | { kind: 'section'; name: string; label?: string; action: 'start'|'end'; span: SourceSpan }
  | { kind: 'comment'; text: string; span: SourceSpan }
  | { kind: 'directive'; name: string; value: string; span: SourceSpan }
  | { kind: 'unsupported'; text: string; span: SourceSpan };
export type ChordDefinition = { name: string; value: string; span: SourceSpan };
export type MusicDocument = { schemaVersion: 1; source: string; metadata: Record<string,string[]>; blocks: MusicBlock[]; definitions: ChordDefinition[]; diagnostics: Diagnostic[] };
