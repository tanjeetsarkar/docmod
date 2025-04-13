import React, { useState } from 'react';

const Toolbar = ({ onAddSection }) => {
  const [newSectionTitle, setNewSectionTitle] = useState('');
  const [showSectionInput, setShowSectionInput] = useState(false);
  
  const handleAddSection = () => {
    if (newSectionTitle.trim()) {
      onAddSection(newSectionTitle);
      setNewSectionTitle('');
      setShowSectionInput(false);
    }
  };
  
  return (
    <div className="document-toolbar">
      <div className="toolbar-group">
        <button 
          className="toolbar-button"
          onClick={() => setShowSectionInput(!showSectionInput)}
        >
          Add New Section
        </button>
        
        {showSectionInput && (
          <div className="section-input">
            <input
              type="text"
              value={newSectionTitle}
              onChange={(e) => setNewSectionTitle(e.target.value)}
              placeholder="Section Title"
            />
            <button onClick={handleAddSection}>Add</button>
            <button onClick={() => setShowSectionInput(false)}>Cancel</button>
          </div>
        )}
      </div>
      
      <div className="toolbar-group">
        <button className="toolbar-button">Export Document</button>
      </div>
    </div>
  );
};

export default Toolbar;