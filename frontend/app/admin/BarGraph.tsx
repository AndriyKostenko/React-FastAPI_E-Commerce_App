'use client'

import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip, Legend} from "chart.js";


ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend);

interface BarGraphProps {
    data: GraphData[];
}


type GraphData = {
    date: string;
    totalAmount: number;
}

const BarGraph: React.FC<BarGraphProps> = ({ data }) => {
    console.log('data in bargrapgh compnent>>>>', data);

    const labels = data.map((item) => item.date);
    const amounts = data.map((item) => item.totalAmount);

    const chartData = {
        labels,
        datasets: [
            {
                label: 'Sale amount',
                data: amounts,
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1,
            }
        ]
    }

    const options = {
        scales: {
            y: {
                beginAtZero: true
            }
        }
    }


    return ( <Bar data={chartData} options={options}></Bar>)
}

export default BarGraph;