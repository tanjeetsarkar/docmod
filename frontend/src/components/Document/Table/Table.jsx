import React, { useState } from 'react';

const Table = ({ table, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editableData, setEditableData] = useState(table.data);
  const [caption, setCaption] = useState(table.caption);
  
  const handleSave = () => {
    setIsEditing(false);
    onUpdate({
      ...table,
      data: editableData,
      caption: caption
    });
  };
  
  const updateCell = (rowIndex, colIndex, value) => {
    const newData = [...editableData];
    newData[rowIndex][colIndex] = value;
    setEditableData(newData);
  };
  
  const addRow = () => {
    if (editableData.length > 0) {
      const newRow = Array(editableData[0].length).fill('');
      setEditableData([...editableData, newRow]);
    }
  };
  
  const addColumn = () => {
    setEditableData(editableData.map(row => [...row, '']));
  };
  
  return (
    <div className="table-container">
      {isEditing ? (
        <div className="table-edit">
          <div className="caption-edit">
            <label>
              Caption:
              <input
                type="text"
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
              />
            </label>
          </div>
          <table className="editable-table">
            <tbody>
              {editableData.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, colIndex) => (
                    <td key={colIndex}>
                      <input
                        type="text"
                        value={cell}
                        onChange={(e) => updateCell(rowIndex, colIndex, e.target.value)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="table-actions">
            <button onClick={addRow}>Add Row</button>
            <button onClick={addColumn}>Add Column</button>
            <button onClick={handleSave}>Save Table</button>
          </div>
        </div>
      ) : (
        <div onClick={() => setIsEditing(true)}>
          <div className="table-caption">{table.caption}</div>
          <table className="display-table">
            <tbody>
              {table.data.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, colIndex) => (
                    <td key={colIndex}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default Table;