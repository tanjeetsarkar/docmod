import React from "react";
import { Section } from "./Section";

export const SectionList = ({ sections, onDelete, onAddSubSection }) => {
    const renderSubSections = (subSections) =>
        subSections.map((subSection, index) => (
            <Section
                key={index}
                section={subSection}
                onDelete={() => onDelete(subSection.id)}
                onAddSubSection={() => onAddSubSection(subSection.id)}
                renderSubSections={renderSubSections}
            />
        ));

    return sections.map((section, index) => (
        <Section
            key={index}
            section={section}
            onDelete={() => onDelete(section.id)}
            onAddSubSection={() => onAddSubSection(section.id)}
            renderSubSections={renderSubSections}
        />
    ));
};