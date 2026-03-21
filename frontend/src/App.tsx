import { BrowserRouter, Routes, Route } from "react-router-dom";
import SubmitPage from "./pages/SubmitPage";
import ProgressPage from "./pages/ProgressPage";
import ResultsPage from "./pages/ResultsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SubmitPage />} />
        <Route path="/progress/:jobId" element={<ProgressPage />} />
        <Route path="/results/:jobId" element={<ResultsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
