using LexerModule;

namespace ParserModule.Nodes;

public sealed class LiteralIntegerExpression : PrimaryExpressionNode
{
    private readonly Token _token;

    public LiteralIntegerExpression(Token token)
    {
        _token = token;
        Value = int.Parse(token.Lexeme);
    }

    public int Value { get; }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitIntegerNumberExpression(this);
    }
}