import React, { useState } from 'react';
import Paragraph from '../Paragraph/Paragraph';
import Table from '../Table/Table';
import Image from '../Image/Image';
import Attachment from '../Attachment/Attachment';

const Section = ({ section, isActive, onContentUpdate, onAddContent }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [sectionTitle, setSectionTitle] = useState(section.title);
  
  const handleSave = () => {
    setIsEditing(false);
    // Would update the section title here in a full implementation
  };
  
  const renderContent = (content) => {
    switch (content.type) {
      case 'paragraph':
        return (
          <Paragraph 
            key={content.id} 
            paragraph={content} 
            onUpdate={(updatedParagraph) => onContentUpdate(content.id, updatedParagraph)}
          />
        );
      case 'table':
        return (
          <Table 
            key={content.id} 
            table={content} 
            onUpdate={(updatedTable) => onContentUpdate(content.id, updatedTable)}
          />
        );
      case 'image':
        return (
          <Image 
            key={content.id} 
            image={content} 
            onUpdate={(updatedImage) => onContentUpdate(content.id, updatedImage)}
          />
        );
      case 'attachment':
        return (
          <Attachment 
            key={content.id} 
            attachment={content} 
            onUpdate={(updatedAttachment) => onContentUpdate(content.id, updatedAttachment)}
          />
        );
      default:
        return null;
    }
  };
  
  // Function to add new paragraph
  const addParagraph = () => {
    const newParagraph = {
      id: `p${Date.now()}`,
      type: 'paragraph',
      runs: [
        { id: `r${Date.now()}`, text: 'New paragraph text.', styles: { bold: false, italic: false } }
      ]
    };
    onAddContent(newParagraph);
  };
  
  // Function to add new table
  const addTable = () => {
    const newTable = {
      id: `t${Date.now()}`,
      type: 'table',
      caption: 'New Table',
      data: [
        ['Header 1', 'Header 2', 'Header 3'],
        ['Data 1', 'Data 2', 'Data 3']
      ]
    };
    onAddContent(newTable);
  };
  
  // Function to add new image
  const addImage = () => {
    const newImage = {
      id: `i${Date.now()}`,
      type: 'image',
      caption: 'New Image',
      src: '/api/placeholder/400/300',
      alt: 'Placeholder image'
    };
    onAddContent(newImage);
  };
  
  // Function to add new attachment
  const addAttachment = () => {
    const newAttachment = {
      id: `a${Date.now()}`,
      type: 'attachment',
      title: 'New Attachment',
      fileType: 'excel',
      data: null // Would contain file reference in a real implementation
    };
    onAddContent(newAttachment);
  };
  
  return (
    <div className={`section level-${section.level} ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <span className="section-number">{section.autoNumber}</span>
        {isEditing ? (
          <div className="section-title-edit">
            <input 
              type="text" 
              value={sectionTitle} 
              onChange={(e) => setSectionTitle(e.target.value)} 
            />
            <button onClick={handleSave}>Save</button>
          </div>
        ) : (
          <h2 
            className="section-title" 
            onClick={() => setIsEditing(true)}
          >
            {section.title}
          </h2>
        )}
      </div>
      
      <div className="section-content">
        {section.content.map(content => renderContent(content))}
      </div>
      
      {isActive && (
        <div className="section-controls">
          <button onClick={addParagraph}>Add Paragraph</button>
          <button onClick={addTable}>Add Table</button>
          <button onClick={addImage}>Add Image</button>
          <button onClick={addAttachment}>Add Attachment</button>
        </div>
      )}
      
      {section.children && section.children.length > 0 && (
        <div className="section-children">
          {section.children.map(childSection => (
            <Section 
              key={childSection.id}
              section={childSection}
              isActive={isActive}
              onContentUpdate={onContentUpdate}
              onAddContent={onAddContent}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default Section;