import React from 'react';
import {createRoot} from 'react-dom/client';
import {App} from './App';

if (new URLSearchParams(location.search).has('feasibility')) {
  void import('./feasibility');
} else {
  createRoot(document.getElementById('root')!).render(<App />);
}
