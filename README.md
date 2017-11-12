# SchoolIdolDetector
Screenshot parser for Love Live! School idol festival game

This is a small utility for detecting the idols that appear in the LLSIF screenshots. So far, it works with Member List and Scout screenshots. It has been optimized for speed, and should take 2-3 secs to parse a screenshot.

### Usage
`python parse.py <image>`

`image` is the screenshot's filename, and can be any format supported by the cv2 library.

### Output
The results are written to the standard output as JSON, while extra information is written to stderr. The results are a list of matches, and each match has the following structure:

```
{
  "card": <API's card data>,
  "idolized": <boolean indicating if the circle's inner pattern corresponds to the idolized card>,
  "relative_h": <circle's height, relative to the image's height>,
  "relative_w": <circle's width, relative to the image's width>,
  "relative_x": <circle's left position, relative to the image's width>,
  "relative_y": <circle's top position, relative to the image's height>
}
```

### Credits
The cards' data and images are obtained from [School Idol Tomodachi](https://schoolido.lu).
