import '../src/app.css'
import '../src/theme/windows-classic.css'

const preview = {
    parameters: {
        layout: 'fullscreen',
        backgrounds: {
            default: 'dark',
            values: [
                { name: 'dark', value: '#0f172a' },
                { name: 'light', value: '#f8f8f8' }
            ]
        },
        options: {
            storySort: {
                order: ['Workflow', 'Sidebar', 'Components', '*']
            }
        }
    }
}

export default preview
