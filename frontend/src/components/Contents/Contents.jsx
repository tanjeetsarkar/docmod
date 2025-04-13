import React, { useCallback, useState } from "react";
import { SectionList } from "./SectionList";

export const Contents = () => {
    const [sections, SetSections] = useState([]);
    const [section, SetSection] = useState({
        id: null,
        content: "",
        subSections: [],
    });

    const handleAddSection = useCallback(() => {
        if (!section.id || !section.content) {
            alert("Both fields are mandatory!");
            return;
        }
        if (sections.some((sec) => sec.id === section.id)) {
            alert("Section ID already exists!");
            return;
        }
        SetSections((prevSections) => [...prevSections, { ...section }]);
        SetSection({ id: null, content: "", subSections: [] });
    }, [section, sections]);

    const handleAddSubSection = useCallback(
        (parentId) => {
            const subSectionId = prompt("Enter Sub-Section ID:");
            const subSectionContent = prompt("Enter Sub-Section Content:");
            if (!subSectionId || !subSectionContent) {
                alert("Both fields are mandatory!");
                return;
            }

            const addSubSection = (sections) =>
                sections.map((sec) => {
                    if (sec.id === parentId) {
                        return {
                            ...sec,
                            subSections: [
                                ...sec.subSections,
                                { id: subSectionId, content: subSectionContent, subSections: [] },
                            ],
                        };
                    }
                    return {
                        ...sec,
                        subSections: addSubSection(sec.subSections),
                    };
                });

            SetSections((prevSections) => addSubSection(prevSections));
        },
        [SetSections]
    );

    const handleDeleteSection = useCallback(
        (id) => {
            const deleteSection = (sections) =>
                sections
                    .filter((sec) => sec.id !== id)
                    .map((sec) => ({
                        ...sec,
                        subSections: deleteSection(sec.subSections),
                    }));

            SetSections((prevSections) => deleteSection(prevSections));
        },
        [SetSections]
    );

    return (
        <div style={{ border: "1px solid white", height: "90vh", width: "25%" }}>
            <div style={{ display: "flex", flexDirection: "column", padding: "4px" }}>
                <input
                    type="text"
                    placeholder="Section ID *"
                    style={{ marginBottom: "8px" }}
                    value={section.id || ""}
                    onChange={(e) => SetSection({ ...section, id: e.target.value })}
                    onKeyDown={(e) => e.key === "Enter" && handleAddSection()}
                />
                <input
                    type="text"
                    placeholder="New Section *"
                    style={{ marginBottom: "8px" }}
                    value={section.content}
                    onChange={(e) => SetSection({ ...section, content: e.target.value })}
                    onKeyDown={(e) => e.key === "Enter" && handleAddSection()}
                />
                <button onClick={handleAddSection}>+</button>
            </div>
            <hr />
            <div style={{ padding: "4px" }}>
                <SectionList
                    sections={sections}
                    onDelete={handleDeleteSection}
                    onAddSubSection={handleAddSubSection}
                />
            </div>
        </div>
    );
};