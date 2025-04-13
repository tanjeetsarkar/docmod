import React, { useState, useEffect } from 'react';
import Section from './Section/Section';
import TableOfContents from './TableOfContents/TableOfContents';
import Toolbar from './Toolbar/Toolbar';

const Document = () => {
    const [documentData, setDocumentData] = useState({
        title: 'Untitled Document',
        sections: [
            {
                id: 's1',
                title: 'Introduction',
                level: 1,
                autoNumber: '1',
                content: [
                    {
                        id: 'p1',
                        type: 'paragraph',
                        runs: [
                            { id: 'r1', text: 'This is the introduction section.', styles: { bold: false, italic: false } }
                        ]
                    }
                ],
                children: [
                    {
                        id: 's2',
                        title: 'Background',
                        level: 2,
                        autoNumber: '1.1',
                        content: [
                            {
                                id: 'p2',
                                type: 'paragraph',
                                runs: [
                                    { id: 'r2', text: 'Background information goes here.', styles: { bold: false, italic: false } }
                                ]
                            }
                        ],
                        children: []
                    }
                ]
            },
            {
                id: 's3',
                title: 'Methods',
                level: 1,
                autoNumber: '2',
                content: [
                    {
                        id: 'p3',
                        type: 'paragraph',
                        runs: [
                            { id: 'r3', text: 'Methods description here.', styles: { bold: false, italic: false } }
                        ]
                    },
                    {
                        id: 't1',
                        type: 'table',
                        caption: 'Table 1: Sample Data',
                        data: [
                            ['Header 1', 'Header 2', 'Header 3'],
                            ['Data 1', 'Data 2', 'Data 3'],
                            ['Data 4', 'Data 5', 'Data 6']
                        ]
                    }
                ],
                children: []
            }
        ]
    });

    const [selectedSection, setSelectedSection] = useState();

    // Flatten the section tree for use in the TOC and navigation
    const flattenSections = (sections, result = []) => {
        sections.forEach(section => {
            result.push({
                id: section.id,
                title: section.title,
                level: section.level,
                autoNumber: section.autoNumber
            });
            if (section.children && section.children.length > 0) {
                flattenSections(section.children, result);
            }
        });
        return result;
    };

    // Find a section by ID in the nested structure
    const findSectionById = (sections, id) => {
        for (const section of sections) {
            if (section.id === id) {
                return section;
            }
            if (section.children && section.children.length > 0) {
                const found = findSectionById(section.children, id);
                if (found) return found;
            }
        }
        return null;
    };

    // Update a section in the nested structure
    const updateSection = (sections, updatedSection) => {
        return sections.map(section => {
            if (section.id === updatedSection.id) {
                return updatedSection;
            }
            if (section.children && section.children.length > 0) {
                return {
                    ...section,
                    children: updateSection(section.children, updatedSection)
                };
            }
            return section;
        });
    };

    // Add a new section
    const addSection = (parentId, newSection) => {
        const updateSections = (sections) => {
            return sections.map(section => {
                if (section.id === parentId) {
                    return {
                        ...section,
                        children: [...section.children, newSection]
                    };
                }
                if (section.children && section.children.length > 0) {
                    return {
                        ...section,
                        children: updateSections(section.children)
                    };
                }
                return section;
            });
        };

        setDocumentData(prevState => ({
            ...prevState,
            sections: updateSections(prevState.sections)
        }));
    };

    // Add content to a section
    const addContent = (sectionId, contentItem) => {
        const section = findSectionById(documentData.sections, sectionId);
        if (section) {
            const updatedSection = {
                ...section,
                content: [...section.content, contentItem]
            };

            setDocumentData(prevState => ({
                ...prevState,
                sections: updateSection(prevState.sections, updatedSection)
            }));
        }
    };

    // Update content in a section
    const updateContent = (sectionId, contentId, updatedContent) => {
        const section = findSectionById(documentData.sections, sectionId);
        if (section) {
            const updatedSection = {
                ...section,
                content: section.content.map(item =>
                    item.id === contentId ? updatedContent : item
                )
            };

            setDocumentData(prevState => ({
                ...prevState,
                sections: updateSection(prevState.sections, updatedSection)
            }));
        }
    };

    // Auto-generate numbers for all sections
    useEffect(() => {
        const numberSections = (sections, prefix = '') => {
            return sections.map((section, index) => {
                const num = prefix ? `${prefix}.${index + 1}` : `${index + 1}`;
                const updatedSection = {
                    ...section,
                    autoNumber: num
                };

                if (section.children && section.children.length > 0) {
                    updatedSection.children = numberSections(section.children, num);
                }

                return updatedSection;
            });
        };

        setDocumentData(prevState => ({
            ...prevState,
            sections: numberSections(prevState.sections)
        }));
    }, []);

    return (
        <div className="document-container">
            <div className="toc-panel">
                <TableOfContents
                    sections={flattenSections(documentData.sections)}
                    selectedSection={selectedSection}
                    onSelectSection={setSelectedSection}
                />
            </div>
            <div className="content-panel">
                <Toolbar
                    onAddSection={(title) => {
                        const newSection = {
                            id: `s${Date.now()}`,
                            title,
                            level: 1,
                            autoNumber: '',
                            content: [],
                            children: []
                        };
                        setDocumentData(prevState => ({
                            ...prevState,
                            sections: [...prevState.sections, newSection]
                        }));
                    }}
                />
                <div className="document-content">
                    {documentData.sections.map(section => (
                        <Section
                            key={section.id}
                            section={section}
                            isActive={selectedSection === section.id}
                            onContentUpdate={(contentId, updatedContent) =>
                                updateContent(section.id, contentId, updatedContent)
                            }
                            onAddContent={(contentItem) => addContent(section.id, contentItem)}
                        />
                    ))}
                </div>
            </div>
        </div>
    );
};

export default Document;