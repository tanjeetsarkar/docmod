// Paragraph.js - Component for handling paragraphs and text runs
import { useState } from 'react';
import TextRun from '../TextRun/TextRun';

const Paragraph = ({ paragraph, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editableRuns, setEditableRuns] = useState(paragraph.runs);
  
  const handleSave = () => {
    setIsEditing(false);
    onUpdate({
      ...paragraph,
      runs: editableRuns
    });
  };
  
  const updateRun = (runId, updatedRun) => {
    setEditableRuns(prev => 
      prev.map(run => run.id === runId ? updatedRun : run)
    );
  };
  
  const addRun = () => {
    const newRun = {
      id: `r${Date.now()}`,
      text: '',
      styles: { bold: false, italic: false }
    };
    setEditableRuns(prev => [...prev, newRun]);
  };
  
  return (
    <div className="paragraph">
      {isEditing ? (
        <div className="paragraph-edit">
          {editableRuns.map(run => (
            <div key={run.id} className="run-edit-container">
              <input
                type="text"
                value={run.text}
                onChange={(e) => updateRun(run.id, { ...run, text: e.target.value })}
              />
              <div className="run-styling">
                <label>
                  <input
                    type="checkbox"
                    checked={run.styles.bold}
                    onChange={(e) => updateRun(run.id, { 
                      ...run, 
                      styles: { ...run.styles, bold: e.target.checked }
                    })}
                  />
                  Bold
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={run.styles.italic}
                    onChange={(e) => updateRun(run.id, { 
                      ...run, 
                      styles: { ...run.styles, italic: e.target.checked }
                    })}
                  />
                  Italic
                </label>
              </div>
            </div>
          ))}
          <div className="paragraph-actions">
            <button onClick={addRun}>Add Text Run</button>
            <button onClick={handleSave}>Save Paragraph</button>
          </div>
        </div>
      ) : (
        <div className="paragraph-content" onClick={() => setIsEditing(true)}>
          {paragraph.runs.map(run => (
            <TextRun key={run.id} run={run} />
          ))}
        </div>
      )}
    </div>
  );
};

export default Paragraph;