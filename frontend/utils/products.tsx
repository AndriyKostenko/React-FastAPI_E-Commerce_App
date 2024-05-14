
//example of products
export const products = [
    {
      id: "64a654593e91b8e73a351e9b",
      name: "iphone 14",
      description: "Short description",
      price: 10,
      brand: "apple",
      category: "Phone",
      inStock: true,
      images: [
        {
          color: "White",
          colorCode: "#FFFFFF",
          image:"data:image/jpeg;base64,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",
        },
        {
          color: "Gray",
          colorCode: "#808080",
          image:
            "https://firebasestorage.googleapis.com/v0/b/e-shop-vid.appspot.com/o/products%2F1694245647731-iphone14-gray.png?alt=media&token=ba0019e0-a6cb-4da7-b214-6252bf57f7e3",
        },
      ],
      reviews: [{rating: 2.5}],
    },
    {
      id: "64a4ebe300900d44bb50628a",
      name: "Logitech MX Keys Advanced Wireless Illuminated Keyboard, Tactile Responsive Typing, Backlighting, Bluetooth, USB-C, Apple macOS, Microsoft Windows, Linux, iOS, Android, Metal Build (Black)",
      description:
        "PERFECT STROKE KEYS - Spherically-dished keys match the shape of your fingertips, offering satisfying feedback with every tap\nCOMFORT AND STABILITY - Type with confidence on a keyboard crafted for comfort, stability, and precision",
      price: 102.99,
      brand: "logitech",
      category: "Accesories",
      inStock: true,
      images: [
        {
          color: "Black",
          colorCode: "#000000",
          image:
            "data:image/jpeg;base64,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",
        },
      ],
      reviews: [
        {
          id: "64a65a6158b470c6e06959ee",
          userId: "6475af156bad4917456e6e1e",
          productId: "64a4ebe300900d44bb50628a",
          rating: 5,
          comment: "good",
          createdDate: "2023-07-06T06:08:33.067Z",
          user: {
            id: "6475af156bad4917456e6e1e",
            name: "Charles",
            email: "example@gmail.com",
            emailVerified: null,
            image:
              "https://lh3.googleusercontent.com/a/AAcHTteOiCtILLBWiAoolIW9PJH-r5825pBDl824_8LD=s96-c",
            hashedPassword: null,
            createdAt: "2023-05-30T08:08:53.979Z",
            updatedAt: "2023-05-30T08:08:53.979Z",
            role: "ADMIN",
          },
        },
      ],
    },
    {
      id: "648437b38c44d52b9542e340",
      name: "Apple iPhone 12, 64GB",
      description:
        'The product is refurbished, fully functional, and in excellent condition .',
      price: 40,
      brand: "Apple",
      category: "Phone",
      inStock: true,
      images: [
        {
          color: "Black",
          colorCode: "#000000",
          image:
            "https://firebasestorage.googleapis.com/v0/b/e-shop-vid.appspot.com/o/products%2Fiphone%2012%20black.png?alt=media&token=8fe19551-173a-4550-9d02-20afffc79b12",
        },
        {
          color: "Blue",
          colorCode: " #0000FF",
          image:
            "https://firebasestorage.googleapis.com/v0/b/e-shop-vid.appspot.com/o/products%2Fiphone%2012%20blue.png?alt=media&token=ede757d2-b631-4451-b80c-123861f16c92",
        },
        {
          color: "Red",
          colorCode: "#FF0000",
          image:
            "https://firebasestorage.googleapis.com/v0/b/e-shop-vid.appspot.com/o/products%2Fiphone%2012%20red.png?alt=media&token=945e1ffb-953e-467a-8325-5a8fbbbf3153",
        },
      ],
      reviews: [
        {
          id: "6499b4887402b0efd394d8f3",
          userId: "6499b184b0e9a8c8709821d3",
          productId: "648437b38c44d52b9542e340",
          rating: 4,
          comment:
            "good enough. I like the camera and casing. the delivery was fast too.",
          createdDate: "2023-06-26T15:53:44.483Z",
          user: {
            id: "6499b184b0e9a8c8709821d3",
            name: "Chaoo",
            email: "example1@gmail.com",
            emailVerified: null,
            image:
              "https://lh3.googleusercontent.com/a/AAcHTtcuRLwWi1vPKaQOcJlUurlhRAIIq2LgYccE8p32=s96-c",
            hashedPassword: null,
            createdAt: "2023-06-26T15:40:52.558Z",
            updatedAt: "2023-06-26T15:40:52.558Z",
            role: "USER",
          },
        },
        {
          id: "6499a110efe4e4de451c7edc",
          userId: "6475af156bad4917456e6e1e",
          productId: "648437b38c44d52b9542e340",
          rating: 5,
          comment: "I really liked it!!",
          createdDate: "2023-06-26T14:30:40.998Z",
          user: {
            id: "6475af156bad4917456e6e1e",
            name: "Charles",
            email: "example@gmail.com",
            emailVerified: null,
            image:
              "https://lh3.googleusercontent.com/a/AAcHTteOiCtILLBWiAoolIW9PJH-r5825pBDl824_8LD=s96-c",
            hashedPassword: null,
            createdAt: "2023-05-30T08:08:53.979Z",
            updatedAt: "2023-05-30T08:08:53.979Z",
            role: "ADMIN",
          },
        },
      ],
    },
    {
      id: "64a4e9e77e7299078334019f",
      name: "Logitech MX Master 2S Wireless Mouse – Use on Any Surface, Hyper-Fast Scrolling, Ergonomic Shape, Rechargeable, Control Upto 3 Apple Mac and Windows Computers, Graphite",
      description:
        "Cross computer control: Game changing capacity to navigate seamlessly on 3 computers, and copy paste text, images, and files from 1 to the other using Logitech flow\nDual connectivity: Use with upto 3 Windows or Mac computers via included Unifying receiver or Bluetooth Smart wireless technology. Gesture button- Yes",
      price: 70,
      brand: "logitech",
      category: "Accesories",
      inStock: true,
      images: [
        {
          color: "Graphite",
          colorCode: " #383838",
          image:
            "data:image/jpeg;base64,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",
        },
      ],
      reviews: [{rating: 1.1}],
    },
    {
      id: "649d775128b6744f0f497040",
      name: 'Smart Watch(Answer/Make Call), 1.85" Smartwatch for Men Women IP68 Waterproof, 100+ Sport Modes, Fitness Activity Tracker, Heart Rate Sleep Monitor, Pedometer, Smart Watches for Android iOS, 2023',
      description:
        'Bluetooth Call and Message Reminder: The smart watch is equipped with HD speaker, after connecting to your phone via Bluetooth, you can directly use the smartwatches to answer or make calls, read messages, store contacts, view call history. The smartwatch can set up more message notifications in "GloryFit" APP. You will never miss any calls and messages during meetings, workout and riding.',
      price: 50,
      brand: "Nerunsa",
      category: "Watch",
      inStock: true,
      images: [
        {
          color: "Black",
          colorCode: "#000000",
          image:
            "https://firebasestorage.googleapis.com/v0/b/e-shop-vid.appspot.com/o/products%2F1695192445608-watch-black.jpg?alt=media&token=4446b901-01ab-4152-8953-e36b22608755",
        },
        {
          color: "Silver",
          colorCode: "#C0C0C0",
          image:
            "https://firebasestorage.googleapis.com/v0/b/e-shop-vid.appspot.com/o/products%2F1695192448311-watch-silver.jpg?alt=media&token=a76bec63-f616-4647-9dd3-b3d23407ba4f",
        },
      ],
      reviews: [{rating: 2.3}],
    },
  ];