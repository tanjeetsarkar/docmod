import React from 'react';

const TableOfContents = ({ sections, selectedSection, onSelectSection }) => {
  return (
    <div className="table-of-contents">
      <h2>Table of Contents</h2>
      <ul className="toc-list">
        {sections.map(section => (
          <li 
            key={section.id}
            className={`toc-item level-${section.level} ${selectedSection === section.id ? 'selected' : ''}`}
            onClick={() => onSelectSection(section.id)}
          >
            <span className="section-number">{section.autoNumber}</span>
            <span className="section-title">{section.title}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default TableOfContents;