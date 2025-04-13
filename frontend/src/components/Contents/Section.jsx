import React from "react";

export const Section = ({ section, onDelete, onAddSubSection, renderSubSections }) => {
    return (
        <div
            style={{
                marginBottom: "8px",
                border: "1px solid gray",
                padding: "4px",
                display: "flex",
                flexDirection: "column",
            }}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                    <strong>ID:</strong> {section.id} <br />
                    <strong>Content:</strong> {section.content}
                </div>
                <div>
                    <button
                        onClick={onDelete}
                        style={{ background: "none", border: "none", cursor: "pointer" }}
                    >
                        🗑️
                    </button>
                    <button
                        onClick={onAddSubSection}
                        style={{ background: "none", border: "none", cursor: "pointer" }}
                    >
                        ➕
                    </button>
                </div>
            </div>
            {section.subSections.length > 0 && (
                <div style={{ marginLeft: "16px", marginTop: "8px" }}>
                    {renderSubSections(section.subSections)}
                </div>
            )}
        </div>
    );
};