import React from 'react';

const TextRun = ({ run }) => {
    const style = {
        fontWeight: run.styles.bold ? 'bold' : 'normal',
        fontStyle: run.styles.italic ? 'italic' : 'normal',
        color: run.styles.color || 'inherit',
        textDecoration: run.styles.underline ? 'underline' : 'none',
    };

    return (
        <span className="text-run" style={style}>
            {run.text}
        </span>
    );
};

export default TextRun;