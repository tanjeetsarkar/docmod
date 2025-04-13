import React, { useState } from 'react';

const Attachment = ({ attachment, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(attachment.title);
  
  const handleSave = () => {
    setIsEditing(false);
    onUpdate({
      ...attachment,
      title: title
    });
  };
  
  const handleFileUpload = (e) => {
    // In a real implementation, this would handle file uploads
    // For now, we'll just simulate it
    console.log('File upload triggered');
  };
  
  const getFileIcon = (fileType) => {
    switch (fileType.toLowerCase()) {
      case 'excel':
        return '📊'; // Excel icon
      case 'pdf':
        return '📄'; // PDF icon
      case 'word':
        return '📝'; // Word icon
      case 'zip':
        return '🗄️'; // ZIP icon
      default:
        return '📎'; // Generic attachment icon
    }
  };
  
  return (
    <div className="attachment-container">
      {isEditing ? (
        <div className="attachment-edit">
          <div className="file-upload">
            <label>
              Upload File:
              <input type="file" onChange={handleFileUpload} />
            </label>
          </div>
          <div className="attachment-fields">
            <label>
              Title:
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
          </div>
          <button onClick={handleSave}>Save</button>
        </div>
      ) : (
        <div className="attachment-display" onClick={() => setIsEditing(true)}>
          <span className="attachment-icon">{getFileIcon(attachment.fileType)}</span>
          <span className="attachment-title">{attachment.title}</span>
          <span className="attachment-type">({attachment.fileType})</span>
        </div>
      )}
    </div>
  );
};

export default Attachment;